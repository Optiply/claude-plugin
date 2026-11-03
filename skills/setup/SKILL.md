---
name: setup
description: Checks and repairs the connections the Optiply plugin needs (the Optiply agent, and optionally the user's own system's connector or a browser for comparing data), walking the user through signing in without ever handling their keys. Use when the user wants to connect Optiply or their own shop, warehouse or ERP system to Claude, when an Optiply tool is missing or returns an authorization error, or before onboarding.
---

# Set up the Optiply connections

Goal: the Optiply agent answers, and every source system the user wants to compare against is reachable read-only. Never ask the user to paste a password, API key or token into the chat. Every sign-in happens in the browser or in the user's own terminal. Claude only reads the user's own system, whatever route it uses; changes there are for the user. In claude.ai chat there is no browser tool: compare from a connector, from export files the user uploads, or switch to Cowork for the browser.

Report progress with this checklist:

```
- [ ] Optiply agent connected
- [ ] Webshop found
- [ ] Own system's connector (optional, read-only)
- [ ] Browser (optional, Cowork and Claude Code)
```

## 1. Optiply agent

The plugin brings the Optiply connector with it (server `optiply`, `https://agent.optiply.com/mcp`). Its tools are `optiply_list_webshops`, `optiply_ask`, `optiply_confirm`, `optiply_cancel` and the onboarding tools. The user only has to connect it once, with their Optiply login.

1. Look for the `optiply_list_webshops` tool on any connected server.
2. **Not there, or asks for authentication:** tell the user to connect it.
   - In claude.ai (web, desktop, mobile) or Cowork: Customize, Plugins, **Optiply**, the **Connectors** tab, **Connect**, and sign in with their Optiply login.
   - In Claude Code: run `/mcp`, pick `optiply`, choose **Authenticate** and sign in with their Optiply login in the browser that opens.
3. **More than one Optiply connector** (the plugin's and one the user added by hand, or Production and Acceptance): use the one that answers, Production unless the user says otherwise, and say which one you use. A server added by hand with `claude mcp add` at the same address can hide the others in Claude Code: remove it with `claude mcp remove <name>`.
4. Tell the user once: Claude asks permission the first time it uses each Optiply tool. "Always allow" is fine for the tools that only read (listing webshops, asking the agent, loading progress); changes are still only made after they approve the change table, and "Allow once" keeps an extra click on applying a change.
5. Probe with `optiply_list_webshops`. If the user has many webshops, add `search` with the name they give.
6. Read the result:
   - Webshops listed: tick the first two items and note the webshop UUID.
   - Authorization error (401, "not authorized", no role): the account is not enabled for the Optiply agent yet. Tell the user to ask their Optiply contact to enable agent access for their login email. Stop here.
   - Rate limit message: tell the user when it resets. Do not retry in a loop.

**No Optiply account** (the user says they do not use Optiply, or the agent keeps answering with an authorization error): do not push them to connect. Questions about how Optiply or one of its integrations works are answered from the public Help Center: `search_help_articles`, then `get_help_article` (server `optiply-docs`, no login). Search with a few key words ("Exact lead time", not a whole sentence); the search already retries with fewer words. When it says the Help Center does not cover a topic, do not search again with other words: say so, and point customers to the Optiply agent and others to Optiply. Answer only from the articles, link each one you use, and say when no article covers the question. For a data check of their own system, offer the `health-check` skill.

## 2. The user's own system (optional, read-only)

Comparisons with the user's shop, warehouse system or ERP are faster in bulk through that system's own connector, if the user already has one in Claude.

1. Look for tools of a connector for the user's system among the connected servers (for example Shopify, Picqer, NetSuite, Zoho Books, Business Central, Odoo, WooCommerce). If there is one, say so in one line and use it only to read.
2. If there is none, mention once that some systems offer one, without pushing it: Shopify, NetSuite and Zoho Books are in Claude's directory (Customize, Connectors, Browse); others, such as Picqer, give a connection URL in their own settings that the user adds as a custom connector (Customize, Connectors, Add custom connector). Ask the Optiply agent or the system's own documentation whether one exists. The browser and export files work just as well.
3. Read only: call only tools that get, list, search, query or read. Never call a tool that creates, updates, deletes, adjusts, cancels or sends, even if the user asks: give the user the steps to make the change in their own system.

## 3. Browser (Cowork and Claude Code, for any source system with a web interface)

Without a connector, the source system's web screens show the same data. Claude only reads them.

1. Look for a browser tool: Claude in Chrome (start Claude Code with `claude --chrome`, or run `/chrome`), or the browser pane of the Claude desktop app.
2. Ask the user to sign in to their source system in that browser themselves. Claude in Chrome uses the sessions already open in their Chrome, but a session can have expired: on a sign-in page, never press Log in, even when the password manager filled it in.
3. Probe: open the product list and read the name and stock of one product.

In claude.ai chat there is no browser tool: offer the user to upload an export, or to switch to Cowork (the Chat/Cowork switch in the message box) so Claude can read their system in their browser. A desktop-only system: an export file.

## Done

Show the ticked checklist and one line on what the user can do next: `/optiply:onboard` right after their first sync, or ask to fix their data at any time.
