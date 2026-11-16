---
name: drive-write
description: Use when the user wants a file uploaded, a OneDrive folder created, or an item deleted ("upload this", "make a folder", "delete that file"). Sends only with --apply. Not for listing - use /drive-list. Input - path, plus the local file or new name.
---
# /drive-write
**Goal:** upload a small file, create one folder, or delete one item.
**Output:** `OK upload`, `OK mkdir`, or `OK deleted`, with the id. Without `--apply` nothing is sent.
`D="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/drive.py"`

## Rules
1. Do not run `bw-secret` yourself. The script reads item `onenote` field `access_token`.
2. Add `--apply` only when the user asked to upload, create, or delete.
3. Delete only the item the user named. Do not delete a parent to remove one file.
4. Do not upload a secret file (tokens, keys, `.env`).

## Steps
1. If the parent folder or item id is unknown, run `/drive-list` first.
2. New folder: `$D mkdir --parent "Folder" --name "New" --apply`.
3. Upload: `$D upload --parent "Folder" --file "/absolute/local/path" --apply`.
4. Delete: `$D delete "Folder/file-or-id" --apply`.
5. Exit code 10 means nothing was sent. If the script prints `ERROR`, stop and report that line.

## Reply
```
<uploaded|created|deleted>: <name> | <id>
```
If nothing was sent: `Not sent. <the PLAN line>`

## Gotchas
- Uploads over 4 MB are refused.
- A 403 that mentions Files.ReadWrite means the saved token cannot change the drive. Stop. Do not retry.

## Before you finish
- [ ] `--apply` was used only because the user asked to change the drive
- [ ] the id in the reply came from an OK line
