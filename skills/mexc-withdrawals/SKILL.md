---
name: mexc-withdrawals
description: Use when the user wants MEXC withdrawal or deposit history. Read only. Does not send a withdrawal. Not the spot balance - use /mexc-balance. Input - from and to dates.
---
# /mexc-withdrawals
**Goal:** list MEXC withdrawals and deposits for a date range. **Input:** `from` and `to` as `YYYY-MM-DD`, and whether they asked for withdrawals, deposits, or both. **Output:** the reply template.
`M="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/mexc.py"`

## Rules
1. Do not open the vault or print the key, secret, signature, or a full address.
2. Read only. Never send a withdrawal or a transfer. This script has no such command.
3. Do not run the script until both dates are known. If one bound is missing, ask and stop.
4. Dates are calendar dates in Europe/Warsaw, inclusive.

## Steps
1. Resolve `from` and `to`.
2. Withdrawals, or both: `$M withdrawals --from YYYY-MM-DD --to YYYY-MM-DD`.
3. Deposits, or both: `$M deposits --from YYYY-MM-DD --to YYYY-MM-DD`.
4. If the script prints `ERROR`, stop and report that line.

## Reply
```
MEXC withdrawals <from> to <to>
- <local time> <amount> <coin> <status> fee <amount> <network> address <mask>
MEXC deposits <from> to <to>
- <local time> <amount> <coin> <status> <network> address <mask>
```

## Gotchas
- Empty output for a valid range is a real result. Say none. Do not widen the range.
- The script walks the range in 29-day windows.
- The printed address and transaction id are masked. Do not reconstruct them.

## Before you finish
- [ ] no withdrawal was sent
- [ ] every row came from the script in this run
- [ ] the reply has no key, secret, full address, or full transaction id
