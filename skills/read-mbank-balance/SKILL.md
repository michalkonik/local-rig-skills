---
name: read-mbank-balance
description: Use when the user asks for the mBank balance or saldo. Reads the Fizen copy of consented mBank accounts. Not for history - use /read-mbank-transactions. Input - optional account name or last digits; say refresh for a live pull.
---
# /read-mbank-balance
**Goal:** report the available and booked balance of each chosen mBank account. **Input:** optional account name or last digits. **Output:** the reply template only. Nothing is written to disk.

Fizen MCP tools: `fizen__list_accounts`, `fizen__get_balance`. `fizen__refresh_account_data` only in step 3.

## Rules
1. Read only. Do not transfer, pay, or call any connect or consent tool.
2. Take account ids only from `fizen__list_accounts` in this run. Never invent one, and never print one.
3. Default to every consented account whose bank is mBank. If the user named one, keep only that match.
4. Call `fizen__refresh_account_data` only when the user asked for fresh, current, or refreshed figures.
5. Quote `asOf` and say whether the figure is the cached copy or a refresh just done.

## Steps
1. Call `fizen__list_accounts` with `{}`. Keep rows whose bank is mBank. No rows: stop and say no mBank account is shared with this assistant.
2. If the user named an account, keep the row whose `name` or masked `account` contains that hint. No match: list the masked accounts and stop.
3. Only if they asked for fresh data: call `fizen__refresh_account_data` with `{"account_ids":["<id>",...]}` for the chosen ids. On error, report it and do not invent a balance.
4. For each chosen id, call `fizen__get_balance` with `{"account_id":"<id>"}`.
5. Reply with the template. Use the masked `account` and `name` from step 1, not the id.

## Reply
```
mBank <account> (<name>)
Available: <available.amount> <available.currency>
Booked: <booked.amount> <booked.currency>
As of: <asOf> (cached|refreshed)
Consent until: <consentValidUntil>
```
One block per account. Add a PLN total only when every account is PLN.

## Gotchas
- `asOf` is when Fizen stored the balance. It is not "right now" unless step 3 ran.
- A refresh is limited to a few pulls per account per day. Do not retry a failed refresh.
- If the tool says the consent expired, say so and stop. Do not guess from an older chat.

## Before you finish
- [ ] every figure came from `fizen__get_balance` in this run
- [ ] the reply has no account id, full number, or token
- [ ] cached or refreshed is stated
