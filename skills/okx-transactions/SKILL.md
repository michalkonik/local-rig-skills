---
name: okx-transactions
description: Use when the user wants OKX account bills or spot fills for a date range. Read only. Not the balance - use /okx-balance. Not withdrawals - use /okx-withdrawals. Input - from, to, and an instrument for fills.
---
# /okx-transactions
**Goal:** list OKX account bills, or spot fills when an instrument is named. **Input:** `from` and `to` as `YYYY-MM-DD`. Fills also need an instrument such as `BTC-USDT`. **Output:** the reply template.
`M="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/okx.py"`

## Rules
1. Do not open the vault or print the key, secret, passphrase, or signature.
2. Do not run the script until both dates are known. If one is missing, ask and stop.
3. Dates are calendar dates in Europe/Warsaw, inclusive. "Last 7 days" means today and the six days before it.
4. Without an instrument, use bills. With an instrument, use fills.

## Steps
1. Resolve `from` and `to`.
2. Bills: `$M bills --from YYYY-MM-DD --to YYYY-MM-DD`. One coin: add `--ccy USDT`.
3. Fills: `$M fills --inst BTC-USDT --from YYYY-MM-DD --to YYYY-MM-DD`.
4. If the script prints `ERROR`, stop and report that line.

## Reply
```
OKX bills <from> to <to>
- <local time> <ccy> change <amount> bal <amount> type <type> <instrument>
OKX fills <instrument> <from> to <to>
- <local time> <buy|sell> <qty> price <price> fee <amount> <ccy>
```

## Gotchas
- Empty output for a valid range is a real result. Say none. Do not widen the range.
- The script walks the range in 7-day windows.
- Instrument ids use a hyphen, as in `BTC-USDT`, not `BTCUSDT`.

## Before you finish
- [ ] the dates and instrument are what the user asked for
- [ ] every row came from the script in this run
- [ ] the reply has no key, secret, passphrase, or signature
