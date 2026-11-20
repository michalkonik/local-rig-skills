---
name: mexc-transactions
description: Use when the user wants MEXC spot trades for one symbol and a date range. Read only. Not the balance - use /mexc-balance. Not withdrawals - use /mexc-withdrawals. Input - symbol, from, and to.
---
# /mexc-transactions
**Goal:** list MEXC spot trades for one symbol, newest first. **Input:** symbol such as BTCUSDT, plus `from` and `to` as `YYYY-MM-DD`. **Output:** the reply template.
`M="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/mexc.py"`

## Rules
1. Do not open the vault or print the key, secret, or signature.
2. Do not run the script until the symbol and both dates are known. If one is missing, ask and stop.
3. Dates are calendar dates in Europe/Warsaw, inclusive. "Last 7 days" means today and the six days before it.

## Steps
1. Resolve the symbol, `from`, and `to`.
2. `$M trades --symbol BTCUSDT --from YYYY-MM-DD --to YYYY-MM-DD`.
3. If the script prints `ERROR`, stop and report that line.

## Reply
```
MEXC trades <symbol> <from> to <to>
- <local time> <buy|sell> <qty> price <price> quote <amount> fee <amount> <asset>
```

## Gotchas
- MEXC trade history requires a symbol. There is no all-symbols ledger in this skill.
- Empty output for a valid range is a real result. Say none. Do not widen the range.
- The script walks the range in 29-day windows.

## Before you finish
- [ ] the symbol and dates are what the user asked for
- [ ] every row came from the script in this run
- [ ] the reply has no key, secret, or signature
