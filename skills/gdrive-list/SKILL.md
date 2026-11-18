---
name: gdrive-list
description: Use when the user wants a Google Drive folder listed or files found on michal.konik.praca@gmail.com ("what's in my Google Drive", "find the sheet"). Not OneDrive - use /drive-list. Not file contents - use /gdrive-read. Input - optional folder path or search words.
---
# /gdrive-list
**Goal:** list one Google Drive folder, or search by name.
**Output:** `OK list` or `OK search`, then one line per item.
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gdrive.py"`

## Rules
1. Do not open `~/Documents/keep/` or print tokens. The script refreshes the saved Drive token.
2. Copy ids and paths from the script. Do not invent them.
3. This account is `michal.konik.praca@gmail.com`. OneDrive stays on `/drive-list`.

## Steps
1. Root: `$G list`. A folder: `$G list "Folder/Sub"`.
2. Find by name: `$G search WORDS`. Inside file text: add `--text` only if a name search is empty.
3. If the script prints `ERROR`, stop and report that line.

## Reply
```
/<path>: <count>
- <dir|doc|sheet|slides|file> <name> | <id>
```

## Gotchas
- Paths are folder names separated by `/`, from My Drive. `list` does not show "Shared with me"; `search` does.
- Duplicate names stop with ERROR. Use the id.
- A 401 means the saved token is dead. Stop. Do not retry.

## Before you finish
- [ ] every id came from the script
- [ ] an ERROR line was quoted, not turned into a success
