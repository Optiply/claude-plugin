#!/usr/bin/env python3
"""Purchasing health check on exports from the user's own system (prospect mode).

Read-only: it only reads the export files and writes result files to --out. Standard library
only (XLSX needs openpyxl), so it runs in claude.ai's code sandbox, in Cowork and in Claude Code.

  python3 health_check.py run --stock stock.csv --sales sales.csv \
      [--orders purchase_orders.csv] [--suppliers suppliers.csv] \
      [--col stock.sku=Artikelcode --col stock.purchase_price=Inkoopprijs ...] \
      [--as-of 2026-10-31] [--holding-cost 0.25] [--month-first] --out results/

  python3 health_check.py selftest

Columns are read by these names unless --col FILE.FIELD=COLUMN says otherwise:
  stock:     sku*, stock*, purchase_price*, sales_price, name, ean, supplier, lot_size, moq
  sales:     sku*, date*, quantity*   (order lines or one row per product per day)
  orders:    order_ref, sku, supplier, order_date, receipt_date, expected_date, open_quantity
  suppliers: supplier, lead_time_days
(* required). A check whose columns are missing is skipped and listed under checks_skipped.

Writes summary.json (totals, top 10 per finding, data quality counts with up to 10 examples,
assumptions, a product-free share_summary) and one CSV per finding with every row.
It diagnoses only: it never computes order quantities, safety stocks or corrected settings.
"""

import argparse
import csv
import json
import math
import os
import re
import statistics
import sys
import tempfile
from collections import defaultdict
from datetime import date, timedelta

TOP = 10
COVER_DAYS = 90          # overstock: stock above 3 months of average daily sales
DEAD_DAYS = 180          # dead stock: no sales in 6 months
MISSED_WINDOW = 90       # missed sales: last 90 days
MIN_SALE_DAYS = 6        # a product "normally sells" when it sold on at least this many days
PAST_DUE_DAYS = 60
SLOW_FACTOR = 1.25       # slow supplier: measured median more than 25% above planned
MIN_RECEIPTS = 3
SPIKE_FACTOR = 10        # a sales day at least 10x the product's usual sales day
SPIKE_MIN_QTY = 5

FIELDS = {
    "stock": ["sku", "stock", "purchase_price", "sales_price", "name", "ean", "supplier", "lot_size", "moq"],
    "sales": ["sku", "date", "quantity"],
    "orders": ["order_ref", "sku", "supplier", "order_date", "receipt_date", "expected_date", "open_quantity"],
    "suppliers": ["supplier", "lead_time_days"],
}
REQUIRED = {"stock": ["sku", "stock", "purchase_price"], "sales": ["sku", "date", "quantity"]}


def read_rows(path):
    """Rows as dicts from CSV (delimiter sniffed, UTF-8 or Latin-1) or XLSX (needs openpyxl)."""
    if path.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError:
            sys.exit(f"{path}: XLSX needs openpyxl here. Save the sheet as CSV and run again.")
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        rows = ws.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(rows)]
        return header, [{h: "" if v is None else str(v) for h, v in zip(header, r)} for r in rows]
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                sample = f.read(65536)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(f, dialect=dialect)
                rows = list(reader)
                return [h.strip() for h in reader.fieldnames or []], [
                    {(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows]
        except UnicodeDecodeError:
            continue
    sys.exit(f"{path}: could not read as UTF-8 or Latin-1.")


def number(value):
    """1234.5, 1.234,50, 1,234.50, 12,5 and EUR 12 all read; empty or junk is None."""
    s = re.sub(r"[^\d,.\-]", "", str(value))
    if not s or s in "-.,":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3}){2,}", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(value, month_first=False):
    v = str(value).strip()
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", v)
    try:
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.match(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", v)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            day, month = (b, a) if month_first else (a, b)
            return date(int(m.group(3)), month, day)
    except ValueError:
        return None
    return None


class Table:
    """One export file with its column mapping; missing optional columns read as absent."""

    def __init__(self, kind, path, overrides):
        self.kind, self.path = kind, path
        self.header, self.rows = read_rows(path)
        self.cols = {f: overrides.get((kind, f), f) for f in FIELDS[kind]}
        lower = {h.lower(): h for h in self.header}
        for f, c in self.cols.items():  # default names match case-insensitively
            if c not in self.header and (kind, f) not in overrides and c.lower() in lower:
                self.cols[f] = lower[c.lower()]
        for f in REQUIRED.get(kind, []):
            if not self.has(f):
                sys.exit(f"{path}: column {self.cols[f]!r} for {kind}.{f} not found. Columns: "
                         f"{', '.join(self.header)}. Map it with --col {kind}.{f}=<column>.")
        for (k, f), c in overrides.items():
            if k == kind and c not in self.header:
                sys.exit(f"{path}: mapped column {c!r} not found. Columns: {', '.join(self.header)}")

    def has(self, field):
        return self.cols.get(field) in self.header

    def get(self, row, field):
        return row.get(self.cols[field], "").strip() if self.has(field) else ""


class Report:
    def __init__(self, out):
        self.out = out
        os.makedirs(out, exist_ok=True)
        self.findings, self.quality, self.skipped = {}, {}, []

    def _write(self, name, header, rows):
        path = os.path.join(self.out, f"{name}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        return path

    def finding(self, name, title, header, rows, euro_col=None, estimate=False):
        if euro_col is not None:
            rows.sort(key=lambda r: -r[euro_col])
        self.findings[name] = {
            "title": title, "estimate": estimate, "count": len(rows),
            "eur": round(sum(r[euro_col] for r in rows)) if euro_col is not None else None,
            "file": self._write(name, header, rows),
            "top": [dict(zip(header, [round(v, 2) if isinstance(v, float) else v for v in r])) for r in rows[:TOP]],
        }

    def check(self, name, title, header, rows, why):
        self.quality[name] = {"title": title, "count": len(rows), "why": why,
                              "file": self._write(f"dq_{name}", header, rows),
                              "examples": [dict(zip(header, r)) for r in rows[:TOP]]}


def run(a):
    overrides = {}
    for spec in a.col or []:
        left, sep, col = spec.partition("=")
        kind, dot, field = left.partition(".")
        if not sep or not dot or kind not in FIELDS or field not in FIELDS[kind]:
            sys.exit(f"--col expects FILE.FIELD=COLUMN with FILE in {', '.join(FIELDS)}, got {spec!r}")
        overrides[(kind, field)] = col.strip()
    st = Table("stock", a.stock, overrides)
    sa = Table("sales", a.sales, overrides)
    po = Table("orders", a.orders, overrides) if a.orders else None
    su = Table("suppliers", a.suppliers, overrides) if a.suppliers else None
    rep = Report(a.out)
    unreadable = defaultdict(int)

    # Sales per product per day.
    daily = defaultdict(lambda: defaultdict(float))
    for r in sa.rows:
        d, q = parse_date(sa.get(r, "date"), a.month_first), number(sa.get(r, "quantity"))
        if d is None or q is None:
            unreadable["sales lines"] += 1
            continue
        daily[sa.get(r, "sku")][d] += q
    all_days = [d for days in daily.values() for d in days]
    if not all_days:
        sys.exit("No readable sales lines: check the date and quantity columns.")
    as_of = date.fromisoformat(a.as_of) if a.as_of else max(all_days)
    start = max(min(all_days), as_of - timedelta(days=364))
    history = (as_of - start).days + 1

    def sold(sku):
        return {d: q for d, q in daily.get(sku, {}).items() if start <= d <= as_of and q > 0}

    # Products.
    products, seen_sku, seen_ean = [], defaultdict(int), defaultdict(list)
    for r in st.rows:
        sku = st.get(r, "sku")
        p = {"sku": sku, "name": st.get(r, "name"), "stock": number(st.get(r, "stock")),
             "pp": number(st.get(r, "purchase_price")), "sp": number(st.get(r, "sales_price")),
             "supplier": st.get(r, "supplier"), "ean": st.get(r, "ean"),
             "lot": number(st.get(r, "lot_size")), "moq": number(st.get(r, "moq"))}
        if p["stock"] is None:
            unreadable["stock rows"] += 1
            p["stock"] = 0.0
        seen_sku[sku] += 1
        if p["ean"]:
            seen_ean[p["ean"]].append(sku)
        days = sold(sku)
        p["qty"] = sum(days.values())
        p["avg"] = p["qty"] / history
        p["last_sale"] = max(days) if days else None
        p["days"] = days
        products.append(p)

    def label(p):
        return [p["sku"], p["name"]]

    # Findings.
    priced = [p for p in products if p["stock"] > 0 and p["pp"]]
    stock_value = sum(p["stock"] * p["pp"] for p in priced)

    dead, over = [], []
    dead_ok = history >= DEAD_DAYS
    for p in priced:
        if dead_ok and (p["last_sale"] is None or (as_of - p["last_sale"]).days >= DEAD_DAYS):
            dead.append(label(p) + [p["stock"], p["pp"], str(p["last_sale"] or "none in file"),
                                    p["stock"] * p["pp"]])
            continue
        excess = p["stock"] - COVER_DAYS * p["avg"]
        if excess > 0:
            months = p["stock"] / (p["avg"] * 30) if p["avg"] else None
            over.append(label(p) + [p["stock"], round(p["avg"] * 30, 1),
                                    round(months, 1) if months else "no sales", excess * p["pp"]])
    rep.finding("overstock", "Stock above 3 months of average sales (excluding dead stock)",
                ["sku", "name", "stock", "avg_sold_per_month", "months_of_stock", "eur_above_3_months"], over, 5)
    if dead_ok:
        rep.finding("dead_stock", "Stock of products with no sales in 6 months",
                    ["sku", "name", "stock", "purchase_price", "last_sale", "eur"], dead, 5)
    else:
        rep.skipped.append(f"dead stock: sales history covers {history} days, needs {DEAD_DAYS}")

    missed, gappy, no_sp = [], [], 0
    window_start = as_of - timedelta(days=MISSED_WINDOW - 1)
    for p in products:
        days = p["days"]
        if len(days) < MIN_SALE_DAYS:
            continue
        gap = history / len(days)
        runs, d, run_start = [], start, None
        while d <= as_of + timedelta(days=1):
            if d <= as_of and d not in days:
                run_start = run_start or d
            elif run_start:
                runs.append((run_start, d - timedelta(days=1)))
                run_start = None
            d += timedelta(days=1)
        lost = []
        for s, e in runs:
            length = (e - s).days + 1
            if e == as_of:  # still not selling today: a stockout only when stock is 0 now
                if p["stock"] > 0 or length < max(3, math.ceil(gap)):
                    continue
            elif length < max(7, math.ceil(3 * gap)):
                continue
            lost.append((s, e))
        if not lost:
            continue
        gappy.append(label(p) + [len(lost), max((e - s).days + 1 for s, e in lost)])
        lost_days = sum((e - s).days + 1 for s, e in lost)
        rate = p["qty"] / max(history - lost_days, 1)
        in_window = sum((e - max(s, window_start)).days + 1 for s, e in lost if e >= window_start)
        if not in_window:
            continue
        if not p["sp"]:
            no_sp += 1
            continue
        missed.append(label(p) + [p["stock"], in_window, round(rate, 2), p["sp"], in_window * rate * p["sp"]])
    rep.finding("missed_sales", "ESTIMATE: sales missed in the last 90 days on products that normally sell",
                ["sku", "name", "stock_now", "days_without_sales", "usual_sold_per_day", "sales_price",
                 "eur_estimate"], missed, 6, estimate=True)

    # Suppliers: measured order-to-receipt vs planned lead time.
    planned = {}
    if su and su.has("supplier") and su.has("lead_time_days"):
        for r in su.rows:
            planned[su.get(r, "supplier")] = number(su.get(r, "lead_time_days"))
    orders = {}
    if po:
        for i, r in enumerate(po.rows):
            key = po.get(r, "order_ref") or f"line {i + 2}"
            o = orders.setdefault(key, {"supplier": "", "ordered": None, "received": None, "expected": None,
                                        "open": False})
            o["supplier"] = o["supplier"] or po.get(r, "supplier")
            od, rd = parse_date(po.get(r, "order_date"), a.month_first), parse_date(po.get(r, "receipt_date"), a.month_first)
            ed = parse_date(po.get(r, "expected_date"), a.month_first)
            o["ordered"] = min(filter(None, [o["ordered"], od]), default=None)
            o["received"] = max(filter(None, [o["received"], rd]), default=None)
            o["expected"] = max(filter(None, [o["expected"], ed]), default=None)
            oq = number(po.get(r, "open_quantity"))
            o["open"] |= (oq or 0) > 0 if po.has("open_quantity") else rd is None
    if po and po.has("order_date") and po.has("receipt_date") and po.has("supplier"):
        measured, from_expected = defaultdict(list), defaultdict(list)
        for o in orders.values():
            if o["ordered"] and o["received"] and o["supplier"]:
                measured[o["supplier"]].append((o["received"] - o["ordered"]).days)
            if o["ordered"] and o["expected"] and o["supplier"]:
                from_expected[o["supplier"]].append((o["expected"] - o["ordered"]).days)
        slow, unplanned = [], []
        for s, lt in measured.items():
            if len(lt) < MIN_RECEIPTS:
                continue
            plan, source = planned.get(s), "supplier list"
            if not plan and from_expected.get(s):
                plan, source = statistics.median(from_expected[s]), "expected dates on orders"
            med = statistics.median(lt)
            if not plan:
                unplanned.append([s, len(lt), med])
            elif med > plan * SLOW_FACTOR:
                slow.append([s, len(lt), med, plan, source, round(med / plan - 1, 2)])
        slow.sort(key=lambda r: -r[5])
        rep.finding("slow_suppliers", "Suppliers whose median order-to-receipt time is more than 25% above plan",
                    ["supplier", "orders_received", "median_days_measured", "planned_days", "planned_from",
                     "share_above_plan"], slow)
        if unplanned:
            rep.findings["slow_suppliers"]["no_plan_to_compare"] = [
                {"supplier": s, "orders_received": n, "median_days_measured": m} for s, n, m in unplanned[:TOP]]
    else:
        rep.skipped.append("slow suppliers: needs purchase orders with supplier, order date and receipt date")

    # Data quality.
    rep.check("duplicate_skus", "Duplicate SKUs", ["sku", "times"],
              sorted([k, n] for k, n in seen_sku.items() if n > 1 and k),
              "The same product twice splits its stock and sales, so neither copy is bought right.")
    if st.has("ean"):
        rep.check("duplicate_eans", "Duplicate EANs", ["ean", "skus"],
                  sorted([e, " | ".join(s)] for e, s in seen_ean.items() if len(s) > 1),
                  "Two products with one barcode mix up receipts and sales.")
    rep.check("negative_stock", "Negative stock", ["sku", "name", "stock"],
              [label(p) + [p["stock"]] for p in products if p["stock"] < 0],
              "Negative stock makes every purchasing calculation order too much or too early.")
    rep.check("stock_no_sales_12m", f"Stock but no sales in the {history} days of history",
              ["sku", "name", "stock"], [label(p) + [p["stock"]] for p in products if p["stock"] > 0 and not p["qty"]],
              "Still active and in stock, yet nothing sold: phase out or check the sales feed.")
    rep.check("no_purchase_price", "Purchase price 0 or empty", ["sku", "name"],
              [label(p) for p in products if not p["pp"]],
              "Without a purchase price, stock value and order value are unknown.")
    if st.has("supplier"):
        rep.check("no_supplier", "Products without a supplier", ["sku", "name"],
                  [label(p) for p in products if not p["supplier"]],
                  "No supplier means no lead time and no purchase advice for this product.")
    else:
        rep.skipped.append("products without a supplier: no supplier column in the stock export")
    if st.has("sales_price"):
        rep.check("sales_below_purchase", "Sales price below purchase price", ["sku", "name", "purchase_price", "sales_price"],
                  [label(p) + [p["pp"], p["sp"]] for p in products if p["sp"] and p["pp"] and p["sp"] < p["pp"]],
                  "Either a loss on every sale or a wrong price, often a case price on a product sold per piece.")
        rep.check("case_price_suspect", "Purchase price at least twice the sales price (looks like a case price)",
                  ["sku", "name", "purchase_price", "sales_price"],
                  [label(p) + [p["pp"], p["sp"]] for p in products if p["sp"] and p["pp"] and p["pp"] >= 2 * p["sp"]],
                  "A case price on a piece product inflates stock value and order value.")
    else:
        rep.skipped.append("price checks: no sales price column")
    if st.has("lot_size") or st.has("moq"):
        filled = [p for p in products if p["lot"] is not None or p["moq"] is not None]
        ones = [label(p) for p in filled if (p["lot"] or 1) == 1 and (p["moq"] or 1) == 1]
        rep.check("lot_moq_all_one", "Lot size and minimum order quantity both 1", ["sku", "name"], ones,
                  "All 1 usually means never filled in; orders then ignore case sizes and supplier minimums.")
        rep.quality["lot_moq_all_one"]["share"] = round(len(ones) / len(filled), 2) if filled else None
    if planned:
        used = {p["supplier"] for p in products if p["supplier"]} | {o["supplier"] for o in orders.values() if o["supplier"]}
        rep.check("supplier_no_lead_time", "Suppliers without a lead time", ["supplier"],
                  [[s] for s in sorted(used) if not planned.get(s)],
                  "Without a lead time, no tool can tell when to order.")
    if po:
        open_orders = [(k, o) for k, o in orders.items() if o["open"]]
        if po.has("expected_date"):
            rep.check("open_po_past_due", f"Open purchase orders more than {PAST_DUE_DAYS} days past due",
                      ["order", "supplier", "expected"],
                      [[k, o["supplier"], str(o["expected"])] for k, o in open_orders
                       if o["expected"] and (as_of - o["expected"]).days > PAST_DUE_DAYS],
                      "They count as incoming stock, so the shortage they hide is never ordered.")
        if po.has("supplier"):
            rep.check("open_po_no_supplier", "Open purchase orders without a supplier", ["order"],
                      [[k] for k, o in open_orders if not o["supplier"]],
                      "Incoming stock nobody can chase or plan.")
    spikes = []
    for p in products:
        if len(p["days"]) >= MIN_SALE_DAYS:
            usual = statistics.median(p["days"].values())
            spikes += [label(p) + [str(d), q, usual] for d, q in sorted(p["days"].items())
                       if q >= max(SPIKE_MIN_QTY, SPIKE_FACTOR * usual)]
    rep.check("sales_spikes", "Sales days far above normal (often one B2B order)",
              ["sku", "name", "date", "quantity", "usual_day"], spikes,
              "One big order read as demand makes every later order too large.")
    rep.check("sales_gaps", "Long stretches without sales on products that normally sell",
              ["sku", "name", "stretches", "longest_days"], gappy,
              "Usually a stockout: the dip is a supply problem, and history read as lower demand orders too little.")

    # Totals, headline, share summary.
    euro = {k: v["eur"] for k, v in rep.findings.items() if v["eur"] is not None}
    headline = max(euro, key=euro.get) if euro else None
    excess = euro.get("overstock", 0) + euro.get("dead_stock", 0)
    totals = {"as_of": str(as_of), "history_days": history, "products": len(products),
              "products_with_sales": sum(1 for p in products if p["qty"]),
              "stock_value_eur": round(stock_value), "headline": headline,
              "yearly_holding_cost_eur": round(excess * a.holding_cost),
              "products_without_purchase_price_excluded": sum(1 for p in products if p["stock"] > 0 and not p["pp"]),
              "missed_sales_skipped_no_sales_price": no_sp,
              "unreadable": dict(unreadable)}
    assumptions = [
        f"Stock value = stock on hand x purchase price; {totals['products_without_purchase_price_excluded']} products in stock without a purchase price are left out.",
        f"Average daily sales = units sold in the {history} days up to {as_of} / {history}.",
        "Overstock = stock above 3 months (90 days) of that average, at purchase price. Dead stock is not counted in it.",
        "Dead stock = products in stock with no sale in the last 6 months (180 days), at purchase price.",
        f"Missed sales (ESTIMATE): products that sold on at least {MIN_SALE_DAYS} days; a stretch without sales of at least 7 days and 3x their usual gap, or stock 0 now, is read as a stockout. Days in the last 90 days x usual daily sales x sales price. Without stock history a quiet stretch can also be low demand.",
        f"Slow suppliers: median days from order date to receipt over at least {MIN_RECEIPTS} received orders, against the supplier's lead time or else the expected dates on its orders; flagged above +25%.",
        f"Yearly holding cost = (overstock + dead stock) x {a.holding_cost:.0%} a year (capital, storage, handling, obsolescence). An assumption, not measured.",
    ]
    def eur(x):
        return f"EUR {x:,}".replace(",", " ")

    lines = [f"Stock value: {eur(totals['stock_value_eur'])}"]
    for k, v in rep.findings.items():
        if v["eur"] is not None:
            lines.append(f"{v['title']}: {eur(v['eur'])} ({v['count']} products)")
        else:
            lines.append(f"{v['title']}: {v['count']}")
    lines.append(f"Yearly holding cost of overstock and dead stock at {a.holding_cost:.0%}: {eur(totals['yearly_holding_cost_eur'])}")
    dq = [f"{v['title']}: {v['count']}" for v in rep.quality.values() if v["count"]]
    lines.append("Data quality: " + ("; ".join(dq) if dq else "no issues found in the checks the exports allow"))
    summary = {"totals": totals, "findings": rep.findings, "data_quality": rep.quality,
               "checks_skipped": rep.skipped, "assumptions": assumptions,
               "share_summary": "\n".join(lines)}
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"as of {as_of}, {history} days of sales, {len(products)} products, stock value EUR {round(stock_value):,}")
    for k, v in rep.findings.items():
        eur = f"EUR {v['eur']:>12,}" if v["eur"] is not None else " " * 16
        print(f"{k:<16} {eur} {v['count']:>6} {'ESTIMATE' if v['estimate'] else ''}")
    for k, v in rep.quality.items():
        print(f"dq {k:<26} {v['count']:>6}")
    for s in rep.skipped:
        print(f"skipped: {s}")
    if unreadable:
        print(f"unreadable: {dict(unreadable)}")
    print(f"headline: {headline}; files in {a.out}")
    return summary


def selftest():
    d = tempfile.mkdtemp()
    as_of = date(2026, 10, 31)
    stock = os.path.join(d, "stock.csv")
    sales = os.path.join(d, "sales.csv")
    orders = os.path.join(d, "orders.csv")
    sups = os.path.join(d, "suppliers.csv")
    with open(stock, "w") as f:
        f.write("SKU;Name;Stock;Purchase price;Sales price;Supplier;EAN\n"
                "A;Steady;150;2,00;5,00;ACME;111\n"      # sells ca. 1.1/day: ca. 50 above 3 months
                "B;Dead;10;3,00;6,00;ACME;222\n"         # last sale 200 days ago -> dead EUR 30
                "C;Out;0;4,00;10,00;BOLT;333\n"          # sold 2/day, nothing in last 20 days, stock 0 -> missed
                "D;NoPrice;5;0;8,00;;333\n"              # no purchase price, no supplier, duplicate EAN
                "D;NoPrice;5;0;8,00;;\n"                 # duplicate SKU
                "E;Neg;-3;1,00;0,50;BOLT;\n")            # negative stock, sales below purchase
    with open(sales, "w") as f:
        f.write("sku,date,quantity\n")
        for i in range(365):
            day = as_of - timedelta(days=i)
            f.write(f"A,{day},1\n")
            if i >= 20:
                f.write(f"C,{day.strftime('%d-%m-%Y')},2\n")
            if i == 200:
                f.write(f"B,{day},1\n")
        f.write(f"A,{as_of - timedelta(days=5)},40\n")  # spike: 41 on one day vs usual 1
    with open(orders, "w") as f:
        f.write("order_ref,supplier,order_date,receipt_date,expected_date\n"
                "P1,ACME,2026-01-01,2026-01-21,2026-01-11\nP2,ACME,2026-02-01,2026-02-21,2026-02-11\n"
                "P3,ACME,2026-03-01,2026-03-21,2026-03-11\nP4,BOLT,2026-04-01,,2026-04-10\n"
                "P5,,2026-10-01,,2026-10-20\n")
    with open(sups, "w") as f:
        f.write("supplier,lead_time_days\nACME,10\nBOLT,\n")
    cols = ["stock.sku=SKU", "stock.stock=Stock", "stock.purchase_price=Purchase price",
            "stock.sales_price=Sales price", "stock.supplier=Supplier", "stock.ean=EAN", "stock.name=Name"]
    s = run(argparse.Namespace(stock=stock, sales=sales, orders=orders, suppliers=sups, col=cols, as_of=None,
                               holding_cost=0.25, month_first=False, out=os.path.join(d, "out")))
    t, fnd, dq = s["totals"], s["findings"], s["data_quality"]
    assert t["as_of"] == "2026-10-31" and t["history_days"] == 365, t
    assert t["stock_value_eur"] == 330, t  # A 300 + B 30; C 0 stock, D no price, E negative
    over = fnd["overstock"]["top"]
    assert len(over) == 1 and over[0]["sku"] == "A", over  # avg (365 + 40) / 365 = 1.11/day
    assert abs(over[0]["eur_above_3_months"] - 2 * (150 - 90 * 405 / 365)) < 0.01, over
    assert fnd["dead_stock"]["eur"] == 30 and fnd["dead_stock"]["top"][0]["sku"] == "B"
    m = fnd["missed_sales"]
    assert m["estimate"] and m["top"][0]["sku"] == "C" and m["top"][0]["days_without_sales"] == 20, m
    assert abs(m["eur"] - 20 * 2 * 10) <= 1, m  # 20 days x 2 a day x EUR 10
    slow = fnd["slow_suppliers"]["top"]
    assert slow == [{"supplier": "ACME", "orders_received": 3, "median_days_measured": 20, "planned_days": 10.0,
                     "planned_from": "supplier list", "share_above_plan": 1.0}], slow
    assert dq["duplicate_skus"]["count"] == 1 and dq["duplicate_eans"]["count"] == 1
    assert dq["negative_stock"]["count"] == 1 and dq["no_purchase_price"]["count"] == 2
    assert dq["no_supplier"]["count"] == 2 and dq["sales_below_purchase"]["count"] == 1
    assert dq["case_price_suspect"]["count"] == 1  # E: 1.00 vs 0.50
    assert dq["supplier_no_lead_time"]["examples"] == [{"supplier": "BOLT"}]
    assert dq["open_po_past_due"]["count"] == 1 and dq["open_po_no_supplier"]["count"] == 1
    assert dq["sales_spikes"]["examples"][0]["sku"] == "A"
    assert t["headline"] == "missed_sales" and t["yearly_holding_cost_eur"] == round((fnd["overstock"]["eur"] + 30) * 0.25)
    assert not any(w in s["share_summary"] for w in ("Steady", "Dead;", "NoPrice")), s["share_summary"]
    assert number("1.234,50") == 1234.5 and number("1,234.50") == 1234.5 and number("12,5") == 12.5
    assert number("EUR 12") == 12 and number("") is None and number("1.234.567") == 1234567
    assert parse_date("31-12-2026") == date(2026, 12, 31) and parse_date("12/31/2026", True) == date(2026, 12, 31)
    assert parse_date("2026-09-03 10:00") == date(2026, 9, 3) and parse_date("junk") is None
    print("selftest ok")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--stock", required=True)
    r.add_argument("--sales", required=True)
    r.add_argument("--orders")
    r.add_argument("--suppliers")
    r.add_argument("--col", action="append", help="FILE.FIELD=COLUMN, e.g. stock.purchase_price=Inkoopprijs")
    r.add_argument("--as-of", help="YYYY-MM-DD; default: the last sales date in the file")
    r.add_argument("--holding-cost", type=float, default=0.25, help="yearly holding cost as a share of stock value")
    r.add_argument("--month-first", action="store_true", help="dates are mm-dd-yyyy (default dd-mm-yyyy)")
    r.add_argument("--out", default="health_check_results")
    sub.add_parser("selftest")
    a = p.parse_args()
    run(a) if a.cmd == "run" else selftest()


if __name__ == "__main__":
    main()
