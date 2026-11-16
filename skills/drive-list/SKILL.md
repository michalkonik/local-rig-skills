---
name: drive-list
description: Use when the user wants a OneDrive folder listed or files found ("what's in my drive", "find the file"). Not for file contents - use /drive-read. Not for upload or delete - use /drive-write. Input - optional folder path or search words.
---
# /drive-list
**Goal:** list one OneDrive folder, or search the drive by name.
**Output:** lines `OK list` or `OK search`, then `- dir|file name | id`.
`D="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/drive.py"`

## Rules
1. Do not run `bw-secret` yourself. The script reads item `onenote` field `access_token`.
2. Copy ids and paths from the script. Do not invent them.
3. Default folder is the drive root.

## Steps
1. Root: `$D list`. A folder: `$D list "Folder/Sub"`.
2. Find by words: `$D search WORDS`.
3. If the script prints `ERROR`, stop and report that line.

## Reply
```
/<path>: <count>
- <dir or file> <name> | <id>
```

## Gotchas
- A 403 that mentions Files.ReadWrite means the saved token was copied before that consent. Stop.
- Paths are folder names separated by `/`, not a full Windows path.

## Before you finish
- [ ] every id came from the script
- [ ] an ERROR line was quoted, not turned into a success
