---
name: gdrive-sheets
description: Use when the user wants a Google Sheet created, a tab added, renamed, or removed, rows appended, or any other Sheets change. Read only for listing tabs. Not OneDrive. Input - spreadsheet id and the change.
---
# /gdrive-sheets
**Goal:** create and change Google Sheets for `michal.konik.praca@gmail.com`. **Input:** the spreadsheet id or path, and the change. **Output:** the script's OK line.
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gdrive.py"`

## Rules
1. Do not open `~/Documents/keep/` or print tokens. Add `--apply` when the user asked for the change.
2. Read exchange and bank figures from their own scripts first. Write only numbers those scripts printed. Do not invent a balance.
3. A missing command is not a reason to refuse. Use `sheet-batch` with one Sheets `batchUpdate` request per object.
4. Do not delete the only tab. Do not trash the spreadsheet unless the user named that file.

## Steps
1. Tabs: `$G sheet-tabs "<id>"`.
2. New file: `$G sheet-create --name "Name" --apply`.
3. New tab: `$G sheet-add-tab "<id>" --name "Tab" --apply`.
4. Rename: `$G sheet-rename-tab "<id>" --old "Old" --new "New" --apply`.
5. Remove: `$G sheet-delete-tab "<id>" --name "Tab" --apply`.
6. One cell or range: `$G sheet-set "<id>" --range "Tab!A1" --values '[["a",1]]' --apply`.
7. Next rows: `$G sheet-append "<id>" --range "Tab!A1" --values '[["2026-11-20","USDT","1"]]' --apply`.
8. Clear: `$G sheet-clear "<id>" --range "Tab!A2:Z" --apply`.
9. Anything else (format, freeze, merge, notes, protection): write a JSON file outside `~/Documents/keep` whose body is `{"requests":[...]}`, then `$G sheet-batch "<id>" --file "/absolute/path.json" --apply`.
10. If the script prints `ERROR`, stop and report that line.

## Reply
```
<created|updated|appended|cleared|renamed|removed>: <name> | <id>
```

## Gotchas
- Without `--apply` nothing is sent. Exit code 10 is the plan, not a failure.
- `sheet-append` adds rows under the used range. Read the tab first so the new row matches its columns.
- Crypto Portfolio 2026 is `12_zryrpEma9EsK-FFSCieOXI7GTiUYKlWUcghk6VVMY`. Other files are named by purpose in USER.md.
- Gate, MEXC, and OKX are read-only. mBank is Fizen. PKO is Enable Banking. Do not place an order or start a payment.

## Before you finish
- [ ] `--apply` was used only because the user asked for the change
- [ ] every figure came from a script in this run
- [ ] the id in the reply came from an OK line
