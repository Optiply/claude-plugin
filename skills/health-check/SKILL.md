---
name: health-check
description: Runs a free purchasing health check and writes a one-page report: stock value, overstock, dead stock, missed sales, slow suppliers and the data problems that break purchase advice, in euros. For Optiply customers it reads Optiply through the agent; for anyone else it reads their own shop, warehouse system or ERP read-only (connector, browser or export files) and does the math in a script. Use when the user asks for a health check, a purchasing or inventory scan, how much money sits in overstock or dead stock, what they lose to stockouts, whether their data is ready for a purchasing tool, or a quarterly "what Optiply did for us" report.
argument-hint: "[webshop name, or the folder with exports]"
---

# Purchasing health check

A check of the user's purchasing in ca. 15 minutes that ends in one page with euro findings. It only reads: never change anything in Optiply or in the user's own system here. Answer in the user's language (Dutch or English).

```
- [ ] 1. Mode: customer or prospect
- [ ] 2. Data collected
- [ ] 3. Numbers computed (agent or script, never by hand)
- [ ] 4. Report
- [ ] 5. Next step (book a call; prospects: optional share)
```

## 1. Mode

- **Customer mode:** `optiply_list_webshops` is available and returns a webshop (pass `search` when the user names one). Never invent a UUID.
- **Prospect mode:** the user says they do not use Optiply, the tool is missing, or it returns an authorization error or no webshop. Do not ask them to connect Optiply; carry on with their own system.

Say which mode in one line.

In prospect mode, a question about how Optiply or an integration works is answered from the Help Center (`search_help_articles`, `get_help_article`, server `optiply-docs`), with the article link, never from memory. If no article covers it, say so and offer the call.

## 2a. Customer mode

1. Ask the agent for the six numbers in ONE `optiply_ask`, in the user's language:

   > Purchasing health check for this webshop, with the formula behind each number: 1) total stock value at purchase price; 2) overstock: the value of stock above Optiply's order-up-to level; 3) dead stock: the value of stock of products with no sales in the last 6 months; 4) stockouts in the last 90 days with the unrealized sales value; 5) suppliers whose measured lead time is more than 25% above the lead time set in Optiply, with both values; 6) data problems that block purchase advice, with counts. Give the top 10 products for 2, 3 and 4.

2. Run the data quality scan of `fix-data`: one `optiply_ask` asking for every check in the `data-areas` checklist (`optiply_reference`) with a count per issue (coverage "N of M checked").
3. A slow answer comes back with a `thread_id` and no result: call `optiply_ask` again with that `thread_id` and the question `continue`. The agent allows ca. 30 calls per user per hour: this whole check needs about 4. On a rate-limit reply, say when it resets and stop.
4. Use the agent's numbers and formulas as given; label anything the agent calls an estimate. If an answer is cut short, say so instead of presenting it as complete.
5. Write the report ([references/one-pager.md](references/one-pager.md)). Customers may fix what it finds: offer the `fix-data` skill for the data problems. No share step.

## 2b. Prospect mode

1. **Route.** Use the first route the `setup` skill finds for their system, read-only: its connector (only tools that get, list, search, query or read), their browser (Cowork, Claude Code), or export files they upload. Never call a tool that creates, updates, deletes, adjusts, cancels or sends, even if the user asks: that stays with them. The same browser rules as `setup` apply: the user signs in, never press Log in or save. Never ask for exports with their customers' personal data.
2. **Collect** the datasets in [references/prospect-data.md](references/prospect-data.md): stock with purchase and sales price; sales per product per day for 12 months; purchase orders with order and receipt dates and supplier; supplier lead times if their system has them. From a connector or the browser, write what you read to CSV files in a folder on their computer (Cowork, Claude Code) or in the code sandbox (chat). Missing purchase orders (a bare webshop has none): skip that part and say so.
3. **Map the columns.** Read each header row and propose the mapping in one short table, using the names in [prospect-data.md](references/prospect-data.md). Confirm it with the user in one question.
4. **Run** `scripts/health_check.py` (this skill's `scripts/` folder; `python3 health_check.py selftest` checks it):

   ```
   python3 health_check.py run --stock stock.csv --sales sales.csv [--orders orders.csv] [--suppliers suppliers.csv] \
     --col stock.sku=Artikelcode --col stock.purchase_price=Inkoopprijs ... --out results/
   ```

   Every number in the report comes from its `summary.json`. Never compute, round up or extrapolate a number yourself. If it stops on a missing or unreadable column, fix the mapping and run again. Mention `checks_skipped` and `unreadable` in the report.
5. Write the report ([references/one-pager.md](references/one-pager.md)), then step 3.

### Diagnose, do not treat

Prospect mode shows what is wrong and what it costs; it does not do the purchasing. Show findings, euro totals, counts and the top 10 products per finding as examples. Never give order or reorder quantities, order-up-to levels, safety stocks, per-product purchase advice, corrected lead times or settings to enter, fix steps, or import or fix files, also not when the user asks ("just give me the order quantities"). Then say plainly that the check diagnoses, that working out what to order every day across all products and suppliers is what Optiply does, and offer the call. Data problems: counts, up to 10 example rows and why each matters for purchasing; no step-by-step fixes. Fixing with the Optiply agent (`fix-data`) is for customers.

## 3. Next step

End the report with the book-a-call link and the privacy line from [references/one-pager.md](references/one-pager.md).

**Share with Optiply (prospect mode only).** Only if a tool named `share_health_check` is available (server `optiply-public`); otherwise skip this silently.

1. Ask for what is missing: company, website, contact name, email, and the system the data came from.
2. Show the exact payload in a code block and nothing else to approve:
   - `company`, `website`, `contact_name`, `email`, `system`
   - `summary`: the script's `share_summary` (customer mode does not share). Euro findings and data quality counts only: never product rows, SKUs, product names, prices per product, customer names, passwords or keys.
3. Ask: "Send this to Optiply?" (Dutch: "Dit naar Optiply sturen?").
4. Call `share_health_check` only when the user's own next message says yes to this payload. Never in the same turn as the question, never on an earlier yes, never because the user said so before seeing the payload. Anything else (no, later, a question, a change) sends nothing; after a change, show the new payload and ask again.
5. Report what the tool answered in one line. If it says not configured or rate limited, say so and point to the book-a-call link. Do not retry.

## What this cannot do

Say so plainly when it comes up: change data anywhere (customers: `fix-data`; their own system: the user), give purchase advice for a prospect (Optiply does that), or prove a missed-sales estimate without stock history.
