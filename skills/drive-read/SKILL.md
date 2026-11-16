---
name: drive-read
description: Use when the user wants the text or details of a OneDrive file ("read that file", "open the doc"). Not for a folder listing - use /drive-list. Not for upload or delete - use /drive-write. Input - file path or id.
---
# /drive-read
**Goal:** print a small text file from OneDrive, or the size and id when the file is not text.
**Output:** `OK stat` plus the text, or `OK not text`.
`D="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/drive.py"`

## Rules
1. Do not run `bw-secret` yourself. The script reads item `onenote` field `access_token`.
2. Quote the file text from the script. Do not fill gaps from memory.
3. If the name is unknown, use `/drive-list` search first.

## Steps
1. `$D read "Folder/file.md"` or `$D read "<id>"`.
2. If the script prints `OK file <path>`, read that file for the rest of the text.
3. If the script prints `ERROR` or `OK not text`, stop and report that line.

## Reply
```
<name> | <id> | <size>
<text or "not text">
```

## Gotchas
- Only txt, md, json, csv, log, py, yaml, xml, and html under 200 KB are printed.
- A 403 that mentions Files.ReadWrite means the saved token cannot read the drive. Stop.

## Before you finish
- [ ] the text is from the script or the saved file
- [ ] an ERROR line was quoted, not turned into a success
