---
name: gdrive-write
description: Use when the user wants a Google Drive file uploaded, a Doc or Sheet replaced, a folder created, or an item trashed ("update the sheet", "upload this"). Sends only with --apply. Not OneDrive - use /drive-write. Input - path or id, plus the local file.
---
# /gdrive-write
**Goal:** upload a file, replace a Doc or Sheet from a local file, write Sheet cells, create one folder, or trash one item.
**Output:** `OK upload`, `OK replace`, `OK sheet-set`, `OK mkdir`, or `OK trashed`. Without `--apply` nothing is sent.
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gdrive.py"`

## Rules
1. Do not open `~/Documents/keep/` or print tokens. Add `--apply` only when the user asked to change the drive.
2. Trash only the item the user named. Do not trash a parent to remove one file.
3. Do not upload tokens, keys, or `.env`. OneDrive writes stay on `/drive-write`.
4. Replace a Sheet with `.xlsx` (a Doc with `.docx` or `.html`). CSV replace needs `--force` because it drops formulas.

## Steps
1. If the parent or item id is unknown, run `/gdrive-list` first.
2. New folder: `$G mkdir --parent "Folder" --name "New" --apply`.
3. New file: `$G upload --parent "Folder" --file "/absolute/local/path" --apply`. A Google Sheet or Doc: add `--as sheet` or `--as doc`.
4. Replace the whole file: `$G replace "<id>" --file "/absolute/local/path" --apply`.
5. Write cells: `$G sheet-set "<id>" --range "Sheet1!A1" --value "text" --apply`.
6. Trash: `$G trash "<id>" --apply`. Exit code 10 means nothing was sent. On `ERROR`, stop.

## Reply
```
<uploaded|replaced|updated|created|trashed>: <name> | <id>
```
If nothing was sent: `Not sent. <the PLAN line>`

## Gotchas
- Replacing a Google Sheet or Doc keeps that type and adds a revision. It does not create a second file.
- `sheet-set` needs the Sheets API. If ERROR says it is disabled, stop. Do not fall back to CSV.
- New spreadsheets, tabs, appended rows, and any other Sheets change are `/gdrive-sheets`, not this skill.
- Docs have no one-paragraph edit here. Download `.docx` with `/gdrive-read`, then `replace`.
- Trash can be restored from the Drive bin. This command does not permanently delete.

## Before you finish
- [ ] `--apply` was used only because the user asked to change the drive
- [ ] the id in the reply came from an OK line
