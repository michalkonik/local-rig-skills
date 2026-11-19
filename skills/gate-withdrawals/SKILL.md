---
name: gate-withdrawals
description: Use when the user wants Gate.io withdrawal or deposit history. Read only. Does not send a withdrawal. Not the spot balance - use /gate-balance. Input - from and to dates.
---
# /gate-withdrawals
**Goal:** list Gate.io withdrawals and deposits for a date range. **Input:** `from` and `to` as `YYYY-MM-DD`, and whether they asked for withdrawals, deposits, or both. **Output:** the reply template.
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gate.py"`

## Rules
1. Do not open the vault or print the key, secret, signature, or a full address.
2. Read only. Never call a withdraw, deposit-address, or transfer command. This script has none.
3. Do not run the script until both dates are known. If one bound is missing, ask and stop.
4. Dates are calendar dates in Europe/Warsaw, inclusive.

## Steps
1. Resolve `from` and `to`. One missing bound: ask and stop.
2. Withdrawals, or both: `$G withdrawals --from YYYY-MM-DD --to YYYY-MM-DD`.
3. Deposits, or both: `$G deposits --from YYYY-MM-DD --to YYYY-MM-DD`.
4. If the script prints `ERROR`, stop and report that line.

## Reply
```
Gate withdrawals <from> to <to>
- <local time> <amount> <currency> <status> fee <amount> <chain> address <mask>
Gate deposits <from> to <to>
- <local time> <amount> <currency> <status> <chain> address <mask>
```

## Gotchas
- Empty output for a valid range is a real result. Say none. Do not widen the range.
- The script walks the range in 29-day windows because Gate rejects a longer window.
- The printed address and transaction id are masked. Do not reconstruct them.

## Before you finish
- [ ] no withdrawal was sent
- [ ] every row came from the script in this run
- [ ] the reply has no key, secret, full address, or full transaction id
