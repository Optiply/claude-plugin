# Data for the prospect check

Four datasets, as CSV or Excel. Product, stock, sales and purchase data is enough: never ask for order lists with their customers' names or addresses. 12 months of sales is the target; less still works (dead stock needs 6 months, and the report says how many days it used).

| File | Script flag | Fields (script name) | Needed for |
|---|---|---|---|
| Stock per product | `--stock` | `sku`*, `stock`*, `purchase_price`*, `sales_price`, `name`, `ean`, `supplier`, `lot_size`, `moq` | Stock value, overstock, dead stock, most data checks |
| Sales per product per day | `--sales` | `sku`*, `date`*, `quantity`* | Overstock, dead stock, missed sales, spikes, gaps |
| Purchase orders | `--orders` | `order_ref`, `sku`, `supplier`, `order_date`, `receipt_date`, `expected_date`, `open_quantity` | Slow suppliers, overdue and supplier-less open orders |
| Suppliers | `--suppliers` | `supplier`, `lead_time_days` | Planned lead time, suppliers without one |

\* required. Sales may be order lines (several per day) or totals per product per day; the script adds them up per day. Totals per month are not enough: ask for a daily report or the order lines. Stock is today's stock on hand for the warehouses they buy for; ask which figure the system calls on hand.

Map a column with `--col FILE.FIELD=COLUMN`, for example `--col stock.purchase_price="Cost per item"`. Columns already named like the script's fields need no mapping. Dates may be ISO (2026-10-31) or day first (31-10-2026); add `--month-first` for 10-31-2026. Numbers may use a decimal comma.

## Column names to look for

Names differ per system, version and language, and a system may need an app or report to export a field. These are names that often appear; always confirm against the file's header row.

| Field | Often called |
|---|---|
| `sku` | SKU, Variant SKU, Artikelcode, Artikelnummer, Productcode, Item code, Item No. |
| `name` | Name, Title, Omschrijving, Description, Productnaam |
| `stock` | Stock, On hand, Available, Free stock, Voorraad, Vrije voorraad, Inventory |
| `purchase_price` | Cost per item, Cost price, Purchase price, Inkoopprijs, Kostprijs, Unit cost |
| `sales_price` | Price, Sales price, Variant price, Verkoopprijs, Regular price |
| `supplier` | Vendor, Supplier, Leverancier, Crediteur |
| `ean` | Barcode, EAN, GTIN |
| `lot_size`, `moq` | Purchase in quantities of, Pack size, Inkoopeenheid; Minimum order quantity, Minimale afname |
| sales `date`, `quantity` | Day, Date, Order date, Datum, Besteldatum; Quantity, Net quantity, Units sold, Aantal |
| orders | Order number, PO number, Ordernummer; Order date, Besteldatum; Expected, Delivery date, Verwacht; Received, Receipt date, Ontvangen; Open quantity, Nog te ontvangen |
| `lead_time_days` | Lead time, Delivery time, Levertijd |

## Where the data usually sits

- **Webshop only** (for example Shopify, WooCommerce, Lightspeed eCom): products with stock and prices, and sales. Usually no purchase orders or lead times: skip slow suppliers and say so. A cost price field may be empty when the shop never used it; that is a finding, not a blocker.
- **Warehouse system** (for example Picqer, Monta): stock, purchase orders with receipts, often suppliers. Sales may come from the webshop instead.
- **ERP** (for example Exact Online, Odoo, Business Central): usually all four, purchase orders with receipt dates included.

When stock and sales live in different systems, take each from the system that holds it and check that the SKUs match on a few products before running.

## From a connector or the browser

Read in batches with read-only tools, then write the four CSV files with the script's field names as headers, so no mapping is needed. For sales, ask the connector for order lines by date range, month by month, and keep only SKU, date and quantity. If 12 months is too much to read this way, take an export instead. In the browser, use the system's own export with the user's OK before each download.
