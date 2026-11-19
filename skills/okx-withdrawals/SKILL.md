---
name: okx-withdrawals
description: Use when the user wants OKX withdrawal or deposit history. Read only. Does not send a withdrawal. Not the balance - use /okx-balance. Input - from and to dates.
---
# /okx-withdrawals
**Goal:** list OKX withdrawals and deposits for a date range. **Input:** `from` and `to` as `YYYY-MM-DD`, and whether they asked for withdrawals, deposits, or both. **Output:** the reply template.
`M="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/okx.py"`

## Rules
1. Do not open the vault or print the key, secret, passphrase, signature, or a full address.
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
OKX withdrawals <from> to <to>
- <local time> <amount> <ccy> state <state> fee <amount> <chain> address <mask>
OKX deposits <from> to <to>
- <local time> <amount> <ccy> state <state> fee <amount> <chain> address <mask>
```

## Gotchas
- Empty output for a valid range is a real result. Say none. Do not widen the range.
- The printed address and transaction id are masked. Do not reconstruct them.
- State is the exchange code. Do not translate it unless the script did.

## Before you finish
- [ ] no withdrawal was sent
- [ ] every row came from the script in this run
- [ ] the reply has no key, secret, passphrase, full address, or full transaction id
