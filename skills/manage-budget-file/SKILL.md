---
name: manage-budget-file
description: Use when the user wants the budget Google Sheet updated from mBank or PKO, or a manual row explained ("update the budget", "add October"). Not the old 2025 file. Input - optional month or date range.
---
# /manage-budget-file
**Goal:** keep the Google Sheet `Budżet 2026` in the 2025 layout: one tab per month, ten category columns, bank rows tagged, manual rows kept.
**Output:** `OK build` or `OK replace`, plus the sheet link.
`B="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/budget.py"`
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gdrive.py"`
`P="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/pko.py"`

## Rules
1. Do not print account ids, full numbers, or tokens. Write the tx JSON under `~/.local/state/rig-skills/` and do not commit it.
2. Categories stay the ten headers from `2025_budget.xlsx`. Do not add a column.
3. A row whose description does not end in `[mbank]` or `[pko]` is manual. Never delete it.
4. Card repayments titled like `SPLATA KARTY` stay below the total. They are not spending.
5. Upload or replace only with `--apply`, and only the file id in `~/.local/state/rig-skills/budget.json`.

## Steps
1. mBank: `/read-mbank-transactions` from the first missing day through today. Save `date, amount, title, category, source: mbank` as JSON. No account id.
2. `$P status`. If it prints `OK no session`, skip PKO and say so. If a session exists, add those txs with `source: pko`.
3. `$B build --txs JSON --out /tmp/budzet.xlsx --note "NOTE"`.
4. First file: `$G upload --file /tmp/budzet.xlsx --name "Budżet 2026" --as sheet --apply`. Save the id into `budget.json`.
5. Later updates: `$G replace ID --file /tmp/budzet.xlsx --apply`. Before that, download the sheet as xlsx and copy manual descriptions back into the JSON.
6. If the script prints `ERROR`, stop.

## Reply
```
Budżet 2026 | <id or link>
<month>: <n> bank rows. PKO: <loaded|skipped, no session>
Manual rows: type an amount and a description in an empty cell of that category. Do not use the [mbank] or [pko] tag.
```

## Gotchas
- Empty rows under each category are for the user. The SUM line includes them.
- Replacing the whole file drops manual rows unless they were copied back in first.
- PKO purchases are missing until `pko.py session` exists. Do not invent them from mBank card repayments.

## Before you finish
- [ ] the sheet link came from an OK upload or replace line
- [ ] PKO was either loaded or reported as skipped
- [ ] no account id or token is in the reply
