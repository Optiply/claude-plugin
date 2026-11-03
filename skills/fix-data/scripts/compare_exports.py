#!/usr/bin/env python3
"""Compare an Optiply export with an export from the user's own system (Monta, an ERP, a webshop).

Read-only: it only reads the two files and writes result files to --out. Standard library only,
so it runs in claude.ai's code sandbox, in Cowork and in Claude Code.

  products: SKU coverage, duplicate keys, stock, active status and supplier per product
    python3 compare_exports.py products --optiply optiply.csv --source monta.csv \
        --key sku=Sku [--stock stock=StockAvailable] \
        [--optiply-active status=0] [--source-active Active=true] \
        [--supplier supplier=SupplierCode] [--field price=PurchasePrice --field lot=LotSize ...] --out results/

  orders: open quantity per SKU, and duplicate SKU lines on one order
    python3 compare_exports.py orders --optiply optiply_lines.csv --source monta_inbounds.csv \
        --key sku=Sku --qty ordered=QuantityOpen [--order order_ref=Reference] \
        [--received received=QuantityReceived] --out results/

  sales: sold quantity per SKU per month (order lines from both systems)
    python3 compare_exports.py sales --optiply optiply_sales.csv --source monta_sales.csv \
        --key sku=Sku --qty quantity=Quantity --date order_date=OrderDate [--day-first] --out results/

  join: several export parts into one file, one row per id, with a count check
    python3 compare_exports.py join part1.csv part2.csv part3.csv --id "Optiply ID" \
        --expect 658646 --out optiply_products.csv

  selftest: python3 compare_exports.py selftest

Mappings are OPTIPLY_COLUMN=SOURCE_COLUMN. Active filters are COLUMN=VALUE[|VALUE...], case-insensitive.
Prints a summary table and writes one CSV per finding plus summary.json.
"""

import argparse
import csv
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict

EXAMPLES = 5


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
                    {(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows
                ]
        except UnicodeDecodeError:
            continue
    sys.exit(f"{path}: could not read as UTF-8 or Latin-1.")


def pair(spec):
    a, sep, b = spec.partition("=")
    if not sep or not a or not b:
        sys.exit(f"Expected OPTIPLY_COLUMN=SOURCE_COLUMN, got {spec!r}")
    return a.strip(), b.strip()


def active_filter(spec):
    if not spec:
        return None
    col, values = pair(spec)
    allowed = {v.strip().lower() for v in values.split("|")}
    return lambda row: row.get(col, "").strip().lower() in allowed


def need(header, col, file_label):
    if col not in header:
        sys.exit(f"Column {col!r} not in {file_label}. Columns: {', '.join(header)}")


def number(value):
    try:
        return float(str(value).replace(",", ".")) if str(value).strip() else 0.0
    except ValueError:
        return None


def loose(key):
    """Key as people mistype it: case, spaces, leading zeros."""
    return key.replace(" ", "").casefold().lstrip("0")


class Report:
    def __init__(self, out):
        self.out, self.summary = out, {}
        os.makedirs(out, exist_ok=True)

    def add(self, name, title, header, rows):
        path = os.path.join(self.out, f"{name}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        self.summary[name] = {"title": title, "count": len(rows), "file": path,
                              "examples": [dict(zip(header, r)) for r in rows[:EXAMPLES]]}

    def finish(self, totals):
        self.summary["_totals"] = totals
        with open(os.path.join(self.out, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)
        print(" | ".join(f"{k}: {v}" for k, v in totals.items()))
        print(f"{'finding':<26} {'count':>9}  example")
        for name, s in self.summary.items():
            if name.startswith("_"):
                continue
            ex = json.dumps(s["examples"][0], ensure_ascii=False)[:90] if s["examples"] else ""
            print(f"{name:<26} {s['count']:>9}  {ex}")
        print(f"files in {self.out}")


def index(rows, col):
    by_key = defaultdict(list)
    for r in rows:
        if r.get(col, "").strip():
            by_key[r[col].strip()].append(r)
    return by_key


def products(a):
    ko, ks = pair(a.key)
    oh, orows = read_rows(a.optiply)
    sh, srows = read_rows(a.source)
    need(oh, ko, "the Optiply file")
    need(sh, ks, "the source file")
    rep = Report(a.out)
    o, s = index(orows, ko), index(srows, ks)

    rep.add("duplicates_optiply", "Key more than once in Optiply", [ko, "times"],
            sorted([k, len(v)] for k, v in o.items() if len(v) > 1))
    rep.add("duplicates_source", "Key more than once in the source", [ks, "times"],
            sorted([k, len(v)] for k, v in s.items() if len(v) > 1))

    only_o = sorted(set(o) - set(s))
    only_s = sorted(set(s) - set(o))
    loose_s = defaultdict(list)
    for k in only_s:
        loose_s[loose(k)].append(k)
    near = [[k, loose_s[loose(k)][0]] for k in only_o if loose(k) in loose_s]
    near_o = {n[0] for n in near}
    near_s = {n[1] for n in near}
    o_active = active_filter(a.optiply_active)
    rep.add("key_differs_in_format", "Same key except case, spaces or leading zeros",
            ["optiply_key", "source_key"], near)
    rep.add("only_in_optiply", "In Optiply, not in the source", [ko, "active_in_optiply"],
            [[k, "" if o_active is None else str(any(o_active(r) for r in o[k]))]
             for k in only_o if k not in near_o])
    rep.add("only_in_source", "In the source, not in Optiply", [ks],
            [[k] for k in only_s if k not in near_s])

    both = sorted(set(o) & set(s))
    if a.stock:
        so, ss = pair(a.stock)
        need(oh, so, "the Optiply file")
        need(sh, ss, "the source file")
        diff = []
        for k in both:
            vo, vs = number(o[k][0].get(so)), number(s[k][0].get(ss))
            if vo is None or vs is None or vo != vs:
                diff.append([k, o[k][0].get(so, ""), s[k][0].get(ss, ""),
                             "" if vo is None or vs is None else vs - vo])
        diff.sort(key=lambda r: -abs(r[3]) if isinstance(r[3], float) else 0)
        rep.add("stock_differs", "Stock differs", [ko, "optiply", "source", "source_minus_optiply"], diff)

    s_active = active_filter(a.source_active)
    if o_active and s_active:
        rep.add("active_status_differs", "Active in one system, inactive in the other",
                [ko, "active_in_optiply", "active_in_source"],
                [[k, o_active(o[k][0]), s_active(s[k][0])] for k in both
                 if o_active(o[k][0]) != s_active(s[k][0])])

    if a.supplier:
        po, ps = pair(a.supplier)
        need(oh, po, "the Optiply file")
        need(sh, ps, "the source file")
        rep.add("supplier_differs", "Supplier differs", [ko, "optiply", "source"],
                [[k, o[k][0].get(po, ""), s[k][0].get(ps, "")] for k in both
                 if o[k][0].get(po, "").strip().casefold() != s[k][0].get(ps, "").strip().casefold()])

    for spec in a.field or []:
        fo, fs = pair(spec)
        need(oh, fo, "the Optiply file")
        need(sh, fs, "the source file")
        rows = []
        for k in both:
            vo, vs = o[k][0].get(fo, ""), s[k][0].get(fs, "")
            no, ns = number(vo), number(vs)
            same = (no == ns) if (vo and vs and no is not None and ns is not None) else (
                vo.strip().casefold() == vs.strip().casefold())
            if not same:
                rows.append([k, vo, vs])
        slug = "".join(c if c.isalnum() else "_" for c in fo.lower()).strip("_")
        rep.add(f"field_{slug}_differs", f"{fo} differs", [ko, "optiply", "source"], rows)

    rep.finish({"optiply_rows": len(orows), "source_rows": len(srows), "keys_in_both": len(both)})
    return rep.summary


def orders(a):
    ko, ks = pair(a.key)
    qo, qs = pair(a.qty)
    oh, orows = read_rows(a.optiply)
    sh, srows = read_rows(a.source)
    for col, header, label in ((ko, oh, "the Optiply file"), (qo, oh, "the Optiply file"),
                               (ks, sh, "the source file"), (qs, sh, "the source file")):
        need(header, col, label)
    rep = Report(a.out)

    def totals(rows, k, q):
        t, bad = Counter(), []
        for r in rows:
            v = number(r.get(q))
            if v is None:
                bad.append(r)
            else:
                t[r.get(k, "").strip()] += v
        return t, bad

    to, bad_o = totals(orows, ko, qo)
    ts, bad_s = totals(srows, ks, qs)
    rep.add("open_qty_differs", "Open quantity per SKU differs",
            [ko, "optiply_open", "source_open", "source_minus_optiply"],
            sorted(([k, to[k], ts[k], ts[k] - to[k]] for k in set(to) | set(ts) if to[k] != ts[k]),
                   key=lambda r: -abs(r[3])))
    if a.order:
        oo, os_ = pair(a.order)
        need(oh, oo, "the Optiply file")
        need(sh, os_, "the source file")
        for rows, k, ocol, name in ((orows, ko, oo, "duplicate_lines_optiply"),
                                    (srows, ks, os_, "duplicate_lines_source")):
            c = Counter((r.get(ocol, ""), r.get(k, "")) for r in rows)
            rep.add(name, "Same SKU twice on one order", ["order", "sku", "lines"],
                    sorted([o_, sku, n] for (o_, sku), n in c.items() if n > 1))
        lines_o = Counter(r.get(oo, "").strip() for r in orows)
        lines_s = Counter(r.get(os_, "").strip() for r in srows)
        rep.add("orders_only_in_optiply", "Open in Optiply, not open in the source", ["order", "lines"],
                sorted([o_, n] for o_, n in lines_o.items() if o_ and o_ not in lines_s))
        rep.add("orders_only_in_source", "Open in the source, not open in Optiply", ["order", "lines"],
                sorted([o_, n] for o_, n in lines_s.items() if o_ and o_ not in lines_o))
        if a.received:
            ro, rs = pair(a.received)
            need(oh, ro, "the Optiply file")
            need(sh, rs, "the source file")
            got_o, got_s = Counter(), Counter()
            for rows, k, ocol, rcol, got in ((orows, ko, oo, ro, got_o), (srows, ks, os_, rs, got_s)):
                for r in rows:
                    got[(r.get(ocol, "").strip(), r.get(k, "").strip())] += number(r.get(rcol)) or 0
            rep.add("received_differs", "Received quantity per order line differs",
                    ["order", "sku", "optiply_received", "source_received"],
                    sorted([o_, sku, got_o[(o_, sku)], got_s[(o_, sku)]]
                           for (o_, sku) in set(got_o) & set(got_s) if got_o[(o_, sku)] != got_s[(o_, sku)]))
    rep.finish({"optiply_lines": len(orows), "source_lines": len(srows),
                "unreadable_quantities": len(bad_o) + len(bad_s)})
    return rep.summary


def month_of(value, day_first=True):
    """YYYY-MM from ISO dates, dd-mm-yyyy (or mm-dd-yyyy) and dates with a time; None if unreadable."""
    import re
    v = str(value).strip()
    m = re.match(r"(\d{4})[-/.](\d{1,2})", v)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", v)
    if m:
        month = int(m.group(2) if day_first else m.group(1))
        return f"{m.group(3)}-{month:02d}" if 1 <= month <= 12 else None
    return None


def sales(a):
    ko, ks = pair(a.key)
    qo, qs = pair(a.qty)
    do, ds = pair(a.date)
    oh, orows = read_rows(a.optiply)
    sh, srows = read_rows(a.source)
    for col, header, label in ((ko, oh, "the Optiply file"), (qo, oh, "the Optiply file"), (do, oh, "the Optiply file"),
                               (ks, sh, "the source file"), (qs, sh, "the source file"), (ds, sh, "the source file")):
        need(header, col, label)
    rep = Report(a.out)
    unreadable = 0

    def per_month(rows, k, q, d):
        nonlocal unreadable
        t = Counter()
        for r in rows:
            month, v = month_of(r.get(d, ""), a.day_first), number(r.get(q))
            if month is None or v is None:
                unreadable += 1
                continue
            t[(r.get(k, "").strip(), month)] += v
        return t

    to, ts = per_month(orows, ko, qo, do), per_month(srows, ks, qs, ds)
    months = sorted({m for _, m in to} | {m for _, m in ts})
    rep.add("sales_per_month", "Total sold per month", ["month", "optiply", "source", "source_minus_optiply"],
            [[m, sum(v for (_, mm), v in to.items() if mm == m), sum(v for (_, mm), v in ts.items() if mm == m),
              sum(v for (_, mm), v in ts.items() if mm == m) - sum(v for (_, mm), v in to.items() if mm == m)]
             for m in months])
    rep.add("sales_differs", "Sold quantity per SKU per month differs",
            [ko, "month", "optiply", "source", "source_minus_optiply"],
            sorted(([k, m, to[(k, m)], ts[(k, m)], ts[(k, m)] - to[(k, m)]] for (k, m) in set(to) | set(ts)
                    if to[(k, m)] != ts[(k, m)]), key=lambda r: -abs(r[4])))
    rep.finish({"optiply_lines": len(orows), "source_lines": len(srows), "months": len(months),
                "unreadable_lines": unreadable})
    return rep.summary


def join(a):
    """Concatenate parts with the same header; drop repeated ids; check the expected total."""
    header, seen, rows, repeated = None, set(), [], 0
    for path in a.parts:
        h, part = read_rows(path)
        if header is None:
            header = h
            need(header, a.id, path)
        elif h != header:
            sys.exit(f"{path}: columns differ from {a.parts[0]}. Ask for every part with the same columns.")
        for r in part:
            key = r.get(a.id, "")
            if key in seen:
                repeated += 1
                continue
            seen.add(key)
            rows.append(r)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    print(f"joined {len(a.parts)} parts: {len(rows)} rows, {repeated} repeated ids dropped -> {a.out}")
    if a.expect is not None and len(rows) != a.expect:
        sys.exit(f"Expected {a.expect} rows, got {len(rows)}: a part is missing or overlaps. Do not compare yet.")
    return len(rows)


def selftest():
    d = tempfile.mkdtemp()
    opt = os.path.join(d, "o.csv")
    src = os.path.join(d, "s.csv")
    with open(opt, "w") as f:
        f.write("sku,stock,status,supplier\nA1,5,0,ACME\nB2,3,0,ACME\nC3,0,1,BOLT\nD4,1,0,X\nD4,1,0,X\n007,2,0,ACME\n")
    with open(src, "w") as f:
        f.write("Sku;StockAvailable;Active;SupplierCode\nA1;5;true;ACME\nB2;4;false;acme\nC3;0;false;Bolt\nE5;9;true;Y\n7;2;true;ACME\n")
    args = argparse.Namespace(optiply=opt, source=src, key="sku=Sku", stock="stock=StockAvailable",
                              optiply_active="status=0", source_active="Active=true",
                              supplier="supplier=SupplierCode", field=None, out=os.path.join(d, "p"))
    s = products(args)
    assert s["duplicates_optiply"]["count"] == 1, s["duplicates_optiply"]
    assert s["key_differs_in_format"]["examples"][0] == {"optiply_key": "007", "source_key": "7"}
    assert s["only_in_optiply"]["count"] == 1 and s["only_in_source"]["count"] == 1
    assert s["stock_differs"]["examples"][0]["sku"] == "B2"
    assert s["active_status_differs"]["count"] == 1  # B2: active in Optiply, inactive in the source
    assert s["supplier_differs"]["count"] == 0  # case only
    with open(opt, "w") as f:
        f.write("order_ref,sku,ordered\nPO1,A1,5\nPO1,A1,2\nPO2,B2,3\n")
    with open(src, "w") as f:
        f.write("Reference,Sku,QuantityOpen\nPO1,A1,7\nPO2,B2,1\n")
    s = orders(argparse.Namespace(optiply=opt, source=src, key="sku=Sku", qty="ordered=QuantityOpen",
                                  order="order_ref=Reference", received=None, out=os.path.join(d, "o")))
    assert s["open_qty_differs"]["count"] == 1 and s["open_qty_differs"]["examples"][0]["sku"] == "B2"
    assert s["duplicate_lines_optiply"]["count"] == 1 and s["duplicate_lines_source"]["count"] == 0
    with open(opt, "w") as f:
        f.write("sku,date,qty\nA1,2026-09-03,2\nA1,2026-09-20 10:00,1\nB2,2026-10-01,4\n")
    with open(src, "w") as f:
        f.write("Sku;OrderDate;Quantity\nA1;03-09-2026;3\nB2;01-10-2026;5\n")
    s = sales(argparse.Namespace(optiply=opt, source=src, key="sku=Sku", qty="qty=Quantity",
                                 date="date=OrderDate", day_first=True, out=os.path.join(d, "s")))
    assert s["sales_differs"]["count"] == 1 and s["sales_differs"]["examples"][0]["sku"] == "B2"
    assert month_of("09/30/2026", day_first=False) == "2026-09" and month_of("junk") is None
    with open(opt, "w") as f:
        f.write("order_ref,sku,ordered,received\nPO1,A1,5,2\nPO3,C3,1,0\n")
    with open(src, "w") as f:
        f.write("Reference,Sku,QuantityOpen,QuantityReceived\nPO1,A1,5,4\nPO4,D4,2,0\n")
    s = orders(argparse.Namespace(optiply=opt, source=src, key="sku=Sku", qty="ordered=QuantityOpen",
                                  order="order_ref=Reference", received="received=QuantityReceived",
                                  out=os.path.join(d, "o2")))
    assert s["orders_only_in_optiply"]["examples"][0]["order"] == "PO3"
    assert s["orders_only_in_source"]["examples"][0]["order"] == "PO4"
    assert s["received_differs"]["count"] == 1
    with open(opt, "w") as f:
        f.write("sku,price,lot\nA1,12.50,6\nB2,3,1\n")
    with open(src, "w") as f:
        f.write("Sku;PurchasePrice;LotSize\nA1;12,5;12\nB2;3;1\n")
    s = products(argparse.Namespace(optiply=opt, source=src, key="sku=Sku", stock=None, optiply_active=None,
                                    source_active=None, supplier=None, field=["price=PurchasePrice", "lot=LotSize"],
                                    out=os.path.join(d, "f")))
    assert s["field_price_differs"]["count"] == 0 and s["field_lot_differs"]["count"] == 1
    p1, p2 = os.path.join(d, "p1.csv"), os.path.join(d, "p2.csv")
    with open(p1, "w") as f:
        f.write("id,sku\n1,A\n2,B\n")
    with open(p2, "w") as f:
        f.write("id,sku\n2,B\n3,C\n")
    n = join(argparse.Namespace(parts=[p1, p2], id="id", expect=3, out=os.path.join(d, "j.csv")))
    assert n == 3
    print("selftest ok")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("products")
    po = sub.add_parser("orders")
    ps = sub.add_parser("sales")
    pj = sub.add_parser("join")
    pj.add_argument("parts", nargs="+")
    pj.add_argument("--id", required=True)
    pj.add_argument("--expect", type=int)
    pj.add_argument("--out", required=True)
    sub.add_parser("selftest")
    for sp in (pp, po, ps):
        sp.add_argument("--optiply", required=True)
        sp.add_argument("--source", required=True)
        sp.add_argument("--key", required=True)
        sp.add_argument("--out", default="compare_results")
    pp.add_argument("--stock")
    pp.add_argument("--optiply-active")
    pp.add_argument("--source-active")
    pp.add_argument("--supplier")
    pp.add_argument("--field", action="append", help="extra OPTIPLY_COLUMN=SOURCE_COLUMN to compare")
    po.add_argument("--qty", required=True)
    po.add_argument("--order")
    po.add_argument("--received")
    ps.add_argument("--qty", required=True)
    ps.add_argument("--date", required=True)
    ps.add_argument("--day-first", action="store_true", default=True, help="dd-mm-yyyy (default)")
    ps.add_argument("--month-first", dest="day_first", action="store_false", help="mm-dd-yyyy")
    a = p.parse_args()
    {"products": products, "orders": orders, "sales": sales, "join": join, "selftest": lambda _a: selftest()}[a.cmd](a)


if __name__ == "__main__":
    main()
