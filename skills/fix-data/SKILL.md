---
name: fix-data
description: Finds and fixes data problems in an Optiply account (products, suppliers, supplier products, stock, sales history, buy orders) by driving the Optiply agent, with every change listed in a table and applied only after the user approves it. Use when the user asks to fix, clean up, check or improve their Optiply data, asks to change data in their own system (Claude gives them the steps), wants their own system (for example Monta or their ERP) checked against Optiply in bulk, says stock, suppliers, prices, sales or purchase advice look wrong, or asks which Optiply features they should be using.
argument-hint: "[area, e.g. products or suppliers]"
---

# Fix my data

The Optiply agent reads the account's live data and makes changes in Optiply. Your job is the order of work, keeping the user oriented, and making sure nothing changes anywhere without their approval of an exact list of changes.

Tools from the user's Optiply connector: `optiply_list_webshops`, `optiply_ask`, `optiply_confirm`, `optiply_cancel`, and `optiply_reference` for the checklists named below (`data-areas`, `field-ownership`, `compare-own-system`, `bulk-import`; Optiply's own, no account data). The connector is added in claude.ai, so the server's name varies (for example "claude.ai Optiply MCP Production"); find the tools by these names. If they are missing or fail to authorize, run the `setup` skill first.

If the user named an area (`$ARGUMENTS`), start there and skip the overview scan.

If the user wants their own system checked against Optiply for many products at once ("compare Monta with Optiply", export files), follow the `compare-own-system` checklist: it compares two exports in code with `scripts/compare_exports.py` and then uses the triage, approval and import rules below.

## Workflow

Copy this checklist into your first reply and keep it updated:

```
- [ ] 1. Webshop picked
- [ ] 2. Source connections checked
- [ ] 3. Overview scan
- [ ] 4. Areas agreed with the user
- [ ] 5. Areas worked through (findings, triage, fixes)
- [ ] 6. Closing table
```

1. **Webshop.** Use `optiply_list_webshops` (with `search` when the user names one). Never invent a UUID.
2. **Source connections.** Check whether this session has a connector for the user's own system (see `setup`, section 2) and say so in one line. Use it only to read, to confirm a mismatch before proposing a fix: only tools that get, list, search, query or read, never ones that create, update, delete, adjust, cancel or send. Never change anything in the user's own system, not even when they ask or say no confirmation is needed: give them the exact steps instead.
3. **Overview scan.** One `optiply_ask` that asks for every check in the `data-areas` checklist at once, with a count per issue. One call, not one per area.
4. **Agree the areas.** Show a table: area, issue, records affected, why it matters for purchase advice. Recommend the order (biggest effect on purchase advice first) and let the user choose.
5. **Per area**, follow its section in the `data-areas` checklist. Start a new thread per area and reuse its `thread_id` inside it. For each issue:
   1. Ask the agent for the affected records, batched ("all products without a supplier", never one ask per product).
   2. Triage each fix by who owns the field, using the `field-ownership` checklist:
      - **Optiply owns it**: ask the agent to propose the fix, then follow the approval rules below.
      - **The user's own system owns it**: do not change it in Optiply, the next sync overwrites it. Give the user the exact steps to change it in their own system.
      - **Integration setting**: tell the user what to ask Optiply support to change, with the affected numbers.
   3. Tick the issue and move on.
6. **Closing table.** One row per issue found: issue, records (N of M checked), result (changed in Optiply, for the user in their own system, raised with Optiply support, not changed), why, owner. Every issue from the overview scan gets a row, including the ones the user chose not to fix. After an import, compare the number of rows in the file with the number of records the agent reads back as changed. Then, if the work turned up signals for an Optiply feature (for example products bought from two suppliers), suggest it as described in the `features` checklist.

## Approval rules (non-negotiable)

Before any change in Optiply, show this table and nothing else as the thing to approve:

| # | Where | Record | Field | Now | After | Why | Reversible? |
|---|---|---|---|---|---|---|---|
| 1 | Optiply | SKU 1234, Blue mug | Lead time (supplier Acme BV) | 21 days | 14 days | Measured deliveries take 14 days | Yes, set it back |

- One row per record and field. "Now" is the value read just before proposing, never a guess. "Reversible?" says how to undo it, or "No" (for example ignoring a product, which is meant to be final). Below the table: the number of changes and the line "Proposal reference: thread <thread_id>", so the right proposal can be applied or cancelled in a later turn.
- For Optiply changes, the agent's reply says **PROPOSAL** and nothing has changed yet. Build the table from that proposal and also show the agent's own wording. If the proposal does not give the current and new value of every record, ask the agent to restate it before asking the user.
- Then ask: "Apply these N changes?" Apply only after the user says yes to this table in their own message. Never in the same turn as the table, and never on the strength of an earlier yes to a different table. If the user approves only some rows, propose again with only those rows.
- Apply with `optiply_confirm`; if the user declines, hesitates or changes the subject, call `optiply_cancel`.
- Just before applying, read each record again. If a value changed since the table was shown, stop and show a new table.
- With more than 5 rows, or any row that is not reversible, apply row 1 first, read it back, show the result, and only then apply the rest.
- After applying, read each record back and report per row: done, or not done and why. Say plainly if a value does not match.
- Log every approval question in the onboarding progress file when one is open ([progress file](../onboard/references/progress-file.md)): which table, what the user answered in their own words, and the result per row. Log a "no" too.
- One open proposal per thread at a time.
- More than 50 records in one fix: no table, no confirm. Prepare an import file as described in the `bulk-import` checklist, or for their own system its own bulk tools, so they only have to check and upload it.

## Working within limits

- The agent allows about 30 calls per user per hour. Batch questions. On a rate-limit reply, tell the user when it resets and stop; do not retry in a loop.
- A slow answer comes back with a `thread_id` and no result: call `optiply_ask` again with the same `thread_id` and the question `continue`.
- If the agent asks a question about the user's data, ask the user. Do not answer it yourself.

## What this cannot do

Say so plainly when it comes up, and point to who can: change integration settings (Optiply support), change data in a source system it cannot write to (the user, with your steps), change stock (counted in the warehouse), or turn on a feature the agent says is not on the plan (Optiply support or their account manager).

## Stop and hand over

Stop and tell the user to contact Optiply support, with the facts you found, when the agent reports a sync or integration failure, when data is missing across the whole account, or when the fix needs a change to the integration itself.
