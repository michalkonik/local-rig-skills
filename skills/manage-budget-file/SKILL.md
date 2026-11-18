---
name: manage-budget-file
description: Use when the user wants the budget Google Sheet updated from mBank or PKO, or a manual row explained ("update the budget", "add October"). Not the old 2025 file. Input - optional month or date range.
---
# /manage-budget-file
**Goal:** keep the Google Sheet `Budżet 2026` in the 2025 layout: one tab per month, ten category columns, an editable monthly budget, bank rows tagged, manual rows kept.
**Output:** `OK build` or `OK replace`, plus the sheet link.
`B="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/budget.py"`
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gdrive.py"`
`P="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/pko.py"`

## Rules
1. Do not print account ids, full numbers, or tokens. Write the tx JSON under `~/.local/state/rig-skills/` and do not commit it.
2. Categories stay the ten headers from `2025_budget.xlsx`. Do not add a column.
3. A row whose description does not end in `[mbank]` or `[pko]` is manual. Never delete it.
4. Card repayments titled like `SPLATA KARTY` stay below the total. They are not spending.
5. Cell B1 on each month tab is the budget, default 9000. The user may change it. `Zostało` is B1 minus spending. Read it back with `$B budgets` before a replace, and pass those values in `--budgets`.
6. Grocery chains are labeled with the chain only (`żabka`, `biedronka`). Other rows keep the shop, person, or purpose.
7. Upload or replace only with `--apply`, and only the file id in `~/.local/state/rig-skills/budget.json`.

## Steps
1. mBank: `/read-mbank-transactions` from the first missing day through today. Save `date, amount, title, counterparty, category, source: mbank` as JSON. No account id.
2. `$P status`. If it prints `OK no session`, skip PKO and say so. If a session exists, add those txs with `source: pko`.
3. Read the calendar from the first day of the range through today. Keep multi-day trips (a city, a flight, or the word wyjazd). Skip birthdays, concerts, and appointments in Kraków. Do not mark a trip longer than 14 days unless the user said to. Save a JSON list of `start`, `end`, and `name`.
4. `$B budgets --xlsx OLD` when the sheet already exists. Then `$B build --txs JSON --trips TRIPS --budgets BUDGETS --out /tmp/budzet.xlsx --note "NOTE"`.
5. First file: `$G upload --file /tmp/budzet.xlsx --name "Budżet 2026.xlsx" --as sheet --apply`. Save the id into `budget.json`.
6. Later updates: `$G replace ID --file /tmp/budzet.xlsx --apply`. Before that, download the sheet as xlsx, copy manual descriptions back into the JSON, and keep each month's B1.
7. If the script prints `ERROR`, stop.

## Reply
```
Budżet 2026 | <id or link>
<month>: <n> bank rows. Budget <amount>. Left <amount>. PKO: <loaded|skipped, no session>
Manual rows: type an amount and a description in an empty cell. Do not use the [mbank] or [pko] tag. The yellow B1 cell is the monthly budget.
```

## Gotchas
- Empty rows under each category are for the user. The SUM line includes them.
- Replacing the whole file drops manual rows and a changed B1 unless they were copied back in first.
- A calendar trip moves that day's spend into `wydatki w podróży`, except subscriptions, therapy, donations, and Revolut top-ups. Grocery labels stay the chain name.
- PKO purchases are missing until `pko.py session` exists. Do not invent them from mBank card repayments.

## Before you finish
- [ ] the sheet link came from an OK upload or replace line
- [ ] PKO was either loaded or reported as skipped
- [ ] no account id or token is in the reply
