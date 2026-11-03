# Progress note

One note per webshop, saved with Optiply through `optiply_save_onboarding_progress` and loaded with `optiply_load_onboarding_progress`, so it works in chat, Cowork and Claude Code and a colleague can continue it. Each save adds a new version and loading returns the newest: always send the whole note. Where those tools are not available, the same note is the file `${CLAUDE_PLUGIN_DATA}/progress/<webshop_uuid>.md` on this computer. Keep this layout.

```
# Onboarding: <webshop name> (<webshop_uuid>)
Goal: <fewer stockouts | less stock tied up | less time ordering | trustworthy data first>
Updated: <YYYY-MM-DD>
Owner after handover: <name, or open>
Re-check on: <YYYY-MM-DD, or open>

## Checklist
- [x] 1. Connections ready, what came in (2026-10-05)
- [ ] 1b. Settings confirmed: warehouses, which sales count, product status, who owns each field, orders sent to the source
- [ ] 2. Open purchase orders match
...

## Findings
| # | Step | Finding | Result | Why | Owner |
|---|---|---|---|---|---|

## Decisions
- 2026-10-05 Change table 1 (3 rows, lead times): approved rows 1-3. Applied: 3 done, 0 not done.

## Open items
- Not sure: which warehouse holds the store stock (step 5).
```

Rules:

- Write dates as `YYYY-MM-DD`, and the date a step was done after its checkbox.
- Every approval question goes under Decisions with the answer in the user's words, including "no" and partial approvals.
- Never store passwords, keys, tokens, or customer personal data (names, addresses, emails of their customers).
- Record whether the user chose to share the summary with Optiply, and when (under Decisions).
