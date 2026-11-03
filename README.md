# Optiply for Claude

Optiply is inventory and purchasing software for e-commerce retailers and wholesalers. This plugin lets you work on your Optiply account with Claude: get onboarded, check that your data came in right, and fix data problems, with every change approved by you first.

## What it does

- **Onboarding.** Once your shop, warehouse system or ERP is connected and the first sync has run, say "Start my Optiply onboarding" (in Claude Code: `/optiply:onboard`). Claude asks your main goal, checks your connection settings with you, compares Optiply with your own system, fixes what is wrong, suggests features that fit, and ends with a first purchase advice you can judge yourself. Your progress is saved with Optiply, so you or a colleague can continue later.
- **Fix my data.** Ask at any time, for example "my suppliers look wrong" or "why do these products have no purchase advice". Claude finds the problems and proposes fixes.
- **Purchasing health check.** Say "Run a purchasing health check" (in Claude Code: `/optiply:health-check`). In ca. 15 minutes you get one page with your stock value, overstock, dead stock, an estimate of missed sales, slow suppliers and the data problems that break purchase advice, in euros. Optiply customers get it from their live Optiply data. Without an Optiply account it reads your own shop, warehouse system or ERP (connector, browser or export files), read-only, and does the math in a script on your side.
- **Questions.** Ask about your stock, purchase advice, suppliers, lead times or service levels. Answers come from your live Optiply data. Without an Optiply account, Claude answers questions about how Optiply and its integrations work from the public Optiply Help Center, with a link to each article it uses.

## Nothing changes without your approval

Every change is listed in a table (what, current value, new value, why) and only made after you say yes. Changes are only made in Optiply. Your own shop, warehouse system or ERP is only read: through its own connector if you have one in Claude, in your browser (Cowork, Claude Code), or from an export you upload. Changes there stay with you; Claude gives you the steps.

The health check sends nothing to Optiply by itself. At the end Claude can offer to send a high-level summary (euro totals and data problem counts, never product rows) to Optiply so someone can follow up; it shows you exactly what would be sent and only sends it after you say yes. That uses a second, login-free connection (`optiply-public`) with that one tool. A third login-free connection (`optiply-docs`, `https://help.optiply.com/mcp`) only reads the public Help Center.

## What you need

- For onboarding, fixing data and questions: an Optiply account with the Optiply agent and AI connections (MCP) switched on. Your Customer Success Manager or Optiply Support can enable it. The health check also works without an Optiply account.
- A Claude Pro, Max, Team or Enterprise plan. Works in Claude on the web, desktop and mobile, in Cowork and in Claude Code.

## Install

1. In Claude: **Customize**, **Plugins**, find **Optiply**, **Add**.
2. Open the plugin's **Connectors** tab, choose **Connect** and sign in with your Optiply login.
3. Say "Start my Optiply onboarding".

On a Team or Enterprise plan, your admin can add the plugin for everyone under Organization settings, Plugins. Claude asks permission the first time it uses each Optiply tool; "Always allow" is fine for the tools that only read.

## Support and privacy

- Help: https://help.optiply.com
- Privacy policy: https://www.optiply.com/en/privacy-policy

## License

[PolyForm Shield 1.0.0](LICENSE), copyright Optiply B.V. You may use and adapt the plugin for your own business; you may not use it to offer a product that competes with Optiply.
