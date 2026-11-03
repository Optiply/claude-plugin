---
name: onboard
description: Guides a new Optiply customer through onboarding once they are fully integrated and the first sync has run. Asks their main goal, checks with them that open orders, assortment, suppliers, stock, sales, prices and supplier settings came in right, compares with the source system (through its connector if the user has one, otherwise in the browser or from an export), fixes the data with their approval, suggests features that fit, and ends with a first purchase advice checked against their own judgement and a go-live check.
disable-model-invocation: true
argument-hint: "[webshop name]"
---

# Onboard an Optiply account

It assumes the customer is fully integrated and the first sync has run; it does not set up or wait for the integration. It follows the order Optiply's onboarders use in their onboarding calls. Checklists named here (`onboarding-questions`, `data-areas`, a connector's name and so on) come from the Optiply connector: call `optiply_reference` with that name. They are Optiply's own onboarding checklists and hold no account data. If `optiply_reference` is not available yet, ask the Optiply agent the same question with `optiply_ask` instead.

Explain Optiply terms in plain words when they come up; the `onboarding-questions` checklist has short answers to the questions customers usually ask.

## 0. Front door

1. Find the webshop (`$ARGUMENTS` is its name if given) with `optiply_list_webshops`.
2. Load the progress note with `optiply_load_onboarding_progress` (format in [references/progress-file.md](references/progress-file.md)). It lives with Optiply, so it works in chat, Cowork and Claude Code, and a colleague can continue it. If that tool is not available, use the file `${CLAUDE_PLUGIN_DATA}/progress/<webshop_uuid>.md` instead; if neither is available (an older connector in chat), keep the note in the conversation and tell the user progress is not saved between chats.
   - **It exists:** show a status of at most five lines: goal, steps done, open items, last update, the next step. Steps done more than 7 days ago, or before a sync the agent reports since, are re-checked with one batched `optiply_ask` before you build on them. Then continue at the first open step.
   - **It does not:** create it, then ask the goal.
3. **Goal.** Before any other agent call or data check, ask with AskUserQuestion: "What do you most want Optiply to do for you?" Options: fewer stockouts, less stock tied up, less time spent ordering, trustworthy data first. Save it. The goal decides emphasis: which areas `fix-data` starts with, which spot-check product to pick, which features to suggest. It never skips a step that blocks the purchase advice (steps 1 to 7, including 1b).

```
- [ ] 1. Connections ready, what came in
- [ ] 1b. Settings confirmed: warehouses, which sales count, product status, who owns each field, orders sent to the source
- [ ] 2. Open purchase orders match
- [ ] 3. Assortment: right products active
- [ ] 4. Suppliers and supplier products complete
- [ ] 5. Spot-check: stock and monthly sales of one product
- [ ] 6. Purchase and sales prices
- [ ] 7. Supplier settings: lead time, reorder period, lot size, MOQ
- [ ] 8. Classification and service levels
- [ ] 9. Data fixed
- [ ] 10. Features that fit
- [ ] 11. First purchase advice and go-live check
```

After every step, save the whole progress note with `optiply_save_onboarding_progress` (or the file, see step 0): findings, the user's answers, decisions, open items. Each save adds a new version and loading returns the newest, so always send the whole note.

## How to ask

For every question in the `onboarding-questions` checklist, first ask the Optiply agent (`optiply_ask`) what it sees, as one batched question with counts per step. Reuse one `thread_id` per step. Then:

- **The data answers it clearly:** do not ask. Say what you found in one line ("All 9 suppliers have a lead time.").
- **The data suggests an answer:** ask the user to confirm, with your suggestion first ("Optiply shows 7 open orders. Is that right?").
- **The data cannot answer it:** ask the open question.

Ask one question at a time. When the answer is a choice, use AskUserQuestion with the recommended option first and a "Not sure" option. "Not sure" is recorded as an open item, not a guess. Without AskUserQuestion (or with nobody to answer), use the recommended option and record it as an open item to confirm.

Use the connector's checklist for what to check with the user. Checklists hold no documentation: they list the settings and comparisons that went wrong in a year of integration support. Facts about how a connector works come only from the agent (see "Connector documentation" below), and when a checklist seems to disagree with the agent, the agent wins. There is one per connector, named after it: shopify, woocommerce, lightspeed, picqer, monta, qls, channeldock, easyecom, exact, odoo, business-central, zoho, sherpaan, tilroy, vendit, and `general` for anything else (NetSuite, Magento, Amazon, Logic4, AFAS, custom API, and more). When more than one system is connected (a webshop and a warehouse system, an ERP and a marketplace), read every checklist, and first ask the agent which one supplies each type of data (products, stock, sales, purchase orders, suppliers, prices, compositions). Ask the user whether anything else writes to Optiply (own scripts or API users, file imports, a partner's feed): a value that changes back by itself usually has a second writer.

### Connector documentation

Never state from memory or from these notes what a connector imports, how often it syncs, what its defaults are or what it sends back: that changes. In step 1, for each connected integration, ask the agent once, in its own thread: "From Optiply's documentation for <connector>: what data comes in, how often each part syncs, which settings exist and their defaults, what goes back to <connector>, and the known limitations. Then: which of those settings are set on this account, and how?" Quote the sources it cites. Use that answer as the facts for every later step, reuse the thread for follow-ups, and re-ask when a later question depends on a detail it did not cover. If the agent has no documentation for the connector, look in the public Help Center (`search_help_articles` and `get_help_article`, server `optiply-docs`) and quote what you use with its link; if that has nothing either, say so, rely on the live settings the agent reports, and record it as an open item for Optiply support.

A mismatch is not fixed yet: note it for step 9, with who owns the fix. When a check cannot be answered because a source is not connected, say which connection would answer it (see `setup`) and move on.

## 1. Connections and data

Run the `setup` skill for the plugin's own connections. Then ask the agent, in one question, which integrations are connected, when each last synced, and how many products, suppliers, supplier products, open purchase orders and sales orders came in. These counts are the baseline for steps 2 to 8. If the agent reports no data at all or a failed sync, the precondition is not met: say what it reported, tell the user to contact Optiply support, save progress, and stop. Then fetch the connector documentation for each connected integration (see "Connector documentation").

## 1b. Settings review

Most integration issues are not bugs but setting choices (warehouses, which orders count, status mappings, which system owns a field), and changing one later may not repair data already imported (ask the agent). So settle them before checking data. Go through section 1b of the `onboarding-questions` checklist and the "Settings to confirm" list in the connector's checklist: ask the agent for the live value of each in one batched question, then confirm or correct each with the user, and record every answer under Decisions in the progress file. A setting the user wants changed is an open item for Optiply support; re-run the checks it affects after the change and the next sync, and ask the agent whether history under the old setting needs a re-import.

## 2 to 8. The checks

Work through sections 2 to 8 of the `onboarding-questions` checklist in order.

Every connector note has a comparison list. Use it during step 5, reading the source system through the first route `setup` found:

1. **A connector for the user's system is connected** (see `setup`, section 2): read through it, in batches, with read tools only.
2. **A browser tool and a source system with a web interface** (Exact Online, Lightspeed, WooCommerce, Odoo, Business Central, Monta, QLS, ChannelDock and most others): open the screens the list needs and read them.
3. **A desktop or legacy system, or no browser:** ask the user to export the report from their system (stock per product, open purchase orders, sales per product per month) to CSV or Excel, and read the file they point you to. For more than a handful of products, compare the full exports with fix-data's bulk comparison (the `compare-own-system` checklist).
4. **No export possible, and computer use is on** (a computer-use tool is available; on Windows only in the Claude desktop app): with the user's go-ahead, open their desktop app and read the same screens.
5. **None of these:** ask the user to look up the values on the list.

In claude.ai chat there is no browser tool. When a check needs the user's system and no connector is connected, offer both: "Upload an export, or switch to Cowork (the Chat/Cowork switch in the message box) and I'll read it in your browser."

Compare on your side, with the same scope on both sides: the same warehouses, the same stock figure (on hand, available, or including stock in transit), the same sales date (order, delivery or invoice) and the same unit. Send only the mismatches that remain to `optiply_ask` to confirm.

**In the browser or a desktop app, read only.** The user signs in themselves; on a sign-in page, ask them to sign in and wait, and never press Log in, even when the browser filled in the form. Never type a password, never press save, submit, delete or any other button that changes data, and type only into search and filter fields. A mismatch found there goes to step 9 like any other, and the user fixes it in their own system. Read products, stock, suppliers and purchase orders; for sales read totals per product, not order lists with their customers' names.

Numbers that look broken across the board (two or more years of stock everywhere, advice of 0 or 1, a very low service level) usually mean demand was not recalculated yet. Ask the agent before treating them as data errors.

If Optiply sends purchase orders to the source, ask the agent in step 4 for the most-bought suppliers and products that have no link to the source system, and for suppliers created by hand in Optiply: an order on them fails or arrives without lines. Note each for step 9, and check in step 11 that the first order arrives with the status, warehouse and order number agreed in 1b.

## 9. Fix the data

Run the `fix-data` skill for this webshop, starting with the mismatches collected in steps 2 to 8 and the areas that matter most for the goal. Fixes in the source system only show up after the next sync; ask the agent how often this connector syncs, and check them again in the next session, not right away.

## 10. Features that fit

Follow the `features` checklist with the signals collected in steps 2 to 9, most relevant to the goal first. Suggest only features the agent confirms are available and not on yet, and switch nothing on without the change table and the user's yes.

## 11. First purchase advice and go-live check

1. **The user's own view first.** Pick one supplier the user knows well and ask: "What would you order from them today, roughly?" Only then ask the agent for Optiply's purchase advice for that supplier and compare. A big difference points back to one of the checks; find which before moving on.
2. Offer to create a first draft order for that supplier (a proposal the user approves, as in `fix-data`).
3. **Go-live check.** Show a table with one row per criterion, each pass, fail or open:
   - Open purchase orders match the user's own count.
   - The spot-check product's stock and monthly sales match, or the difference is explained.
   - Every supplier with active products has a lead time.
   - Purchase prices are filled in for the products bought most.
   - The first purchase advice made sense to the user.
   Live when all pass. Otherwise list what blocks it and who owns it.
4. **Handover.** Ask who keeps suppliers, lead times and prices up to date from now on, and save their name. Save a re-check date about two weeks out, after at least one sync, and tell the user to run `/optiply:onboard` again then.
5. **Closing table.** One row per finding from the whole onboarding: finding, result (changed in Optiply, for the user in their own system, raised with Optiply support, not changed), why, owner. Include the features the user chose to look at. Save it in the progress file.
6. **Share with Optiply (opt-in).** Ask with AskUserQuestion, in the user's language:

   > Shall I share this onboarding summary with Optiply? Then the Optiply team knows your goal, the choices you made and what is still open, so whoever helps you next is fully prepared and you never have to explain your setup twice. It contains no passwords and no details about your own customers.

   Options: "Yes, share it" (recommended), "Show me first", "No, keep it on this computer".
   - **Show me first:** show exactly what would be sent (the summary below), then ask again.
   - **Yes:** send it with the connector's `optiply_save_onboarding_summary` tool. If the connector does not have that tool yet, say sharing is not available yet and that the summary stays on this computer.
   - **No:** send nothing, and record the choice under Decisions.

   Call it with `user_consented: true` and a `summary` with exactly these fields: `goal`, `owner_after_handover` (a role, not a name), `recheck_on` (YYYY-MM-DD), `findings` (each `finding`, `result`, `why`, `owner`, from the closing table), `open_items`, `decisions` (with the user's answers). Nothing else is sent. Leave out names of people outside the account's own team, any customer of theirs, and any password, key or token; Optiply also removes email addresses, phone numbers and account numbers on arrival.

Onboarding is done when the go-live check passes and the user has seen one real purchase advice that made sense to them.

## What this cannot do

Say so plainly when it comes up, and point to who can:

- Change the integration's settings (warehouses, statuses, start dates): Optiply support.
- Fix data in a source system it cannot write to: the user, with the steps you give.
- Switch on features or plans the agent says are not available: Optiply support or their account manager.
- Correct stock: stock is counted in the warehouse.
