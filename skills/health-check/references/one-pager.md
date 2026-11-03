# The one-page result

One page, in the user's language. Numbers only from the agent (customer mode) or `summary.json` (prospect mode), rounded to whole euros. Every estimate says "estimate" next to the number. Plain and factual: no exclamation marks, no sales language.

## Order

1. **Headline.** The biggest euro number first, in one sentence: "EUR 7 704 sits in stock above 3 months of sales." Then the stock value, and the yearly holding cost of overstock and dead stock with its assumption (prospect: `yearly_holding_cost_eur`, 25% a year unless the user gives their own; customer: only when the agent gives one).
2. **Findings table**, biggest euro first: finding, euros, products, estimate or measured.
3. **Top 10 per finding**: overstock, dead stock, missed sales (SKU, name, the number behind it, euros), slow suppliers (supplier, measured, planned). Fewer rows when fewer exist.
4. **Data that breaks purchase advice**: one row per check with a count, up to 10 examples, and the `why` in one line. Prospect mode: when there are problems, add "Your data is not ready for any purchasing tool, including one you would build yourself." with the counts. No fix steps (see "Diagnose, do not treat" in SKILL.md); customers get the offer to fix them with `fix-data`.
5. **How these numbers were made**: the assumptions list, which numbers are estimates, the history used (`history_days`, `as_of`), and the checks skipped for lack of data.
6. **Closing** (prospect mode), in substance:
   > This is a snapshot. A one-off clean-up does not keep it this way: data drifts back as products, prices and suppliers change, and the real work is the daily decision of what to order, across every product and supplier. That is what Optiply does. Run this check again in 3 months to see what came back, or talk it through with us.

   Customer mode: what changed since the last check if the user has one, and what Optiply flags to act on next.
7. **Book a call** and the **privacy line**, below.

## Book a call

<!-- PLACEHOLDER: replace with Wiebe's own HubSpot meetings link once it is known; until then the public demo page. -->
- English: https://www.optiply.com/en/demo
- Dutch: https://www.optiply.com/nl/demo

Prospect mode: "Book a call with Wiebe from Optiply to go through these findings: <link>". Customer mode: "Questions about these numbers? Ask your Optiply contact or book a call: <link>".

## Privacy line

Add once, at the end (prospect mode):

- English: "Your data was read on your side and stays in this conversation. Nothing goes to Optiply unless you say yes to the exact summary shown; Optiply then stores your contact details and that summary to follow up. Privacy policy: https://www.optiply.com/en/privacy-policy"
- Dutch: "Je gegevens zijn aan jouw kant gelezen en blijven in dit gesprek. Er gaat niets naar Optiply tenzij je ja zegt op de exacte samenvatting die je te zien krijgt; Optiply bewaart dan je contactgegevens en die samenvatting om contact op te nemen. Privacybeleid: https://www.optiply.com/nl/privacy-policy"

## Dutch headings

Kernbevinding, Bevindingen, Top 10 per bevinding, Data die het inkoopadvies breekt, Hoe deze cijfers zijn berekend, Volgende stap. Use "schatting" for estimate, "overvoorraad", "incourante voorraad" (dead stock), "gemiste omzet" (missed sales), "levertijd".
