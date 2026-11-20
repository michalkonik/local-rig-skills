---
name: gdrive-read
description: Use when the user wants a Google Drive file read or downloaded ("read that doc", "download the sheet"). Docs and Sheets are saved locally. Not a folder listing - use /gdrive-list. Not OneDrive - use /drive-read. Input - path or file id, optional format.
---
# /gdrive-read
**Goal:** preview a Doc or small text file, or download a file to this machine.
**Output:** `OK read` / `OK stat` plus a short preview, or `OK download` plus the local path.
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gdrive.py"`

## Rules
1. Do not open `~/Documents/keep/` or print tokens. The script refreshes the saved Drive token.
2. Quote only text the script printed, or text you then read from the local path it printed.
3. If the name is unknown, use `/gdrive-list` first. OneDrive is `/drive-read`.

## Steps
1. Preview: `$G read "Folder/file"` or `$G read "<id>"`.
2. Download: `$G download "<id>"`. Sheets become `.xlsx`, Docs `.docx`, Slides `.pptx`.
3. Other formats: `--format csv|txt|html|pdf`. csv and txt are values or plain text, not formulas.
4. One range of a Sheet: `$G sheet-get "<id>" --range "Sheet1!A1:C20"`.
5. If the script prints `OK file <path>`, read that file only when it is under 200 KB. If it prints `ERROR`, stop.

## Reply
```
<name> | <id> | <local path or "not text">
<short preview>
```

## Gotchas
- A Sheet csv preview drops formulas. Download `.xlsx` before any edit.
- Google export fails above 10 MB. Say so; do not invent the contents.
- Do not paste a large private file into the chat. Give the path and a short preview.
- `sheet-get` needs the Sheets API. If ERROR says the API is disabled, stop and report that line.
- Tab names are `$G sheet-tabs "<id>"`. Creating or changing a tab is `/gdrive-sheets`.

## Before you finish
- [ ] the preview came from the script or the saved file
- [ ] an ERROR line was quoted, not turned into a success
