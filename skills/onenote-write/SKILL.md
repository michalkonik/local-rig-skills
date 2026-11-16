---
name: onenote-write
description: Use when the user wants a new OneNote page or text added to an existing page ("save this to OneNote", "append to the note"). Sends only with --apply. Not for reading - use /onenote-read. Input - section or page, title, and the text.
---
# /onenote-write
**Goal:** create a page in a section, or append paragraphs to an existing page.
**Output:** `OK created` or `OK appended` with the page id. Without `--apply` nothing is sent.
`N="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/onenote.py"`

## Rules
1. Do not run `bw-secret` yourself. The script reads item `onenote` field `access_token`.
2. Add `--apply` only when the user asked to save or append. A preview request stays without it.
3. Put the note body in `--text` or `--file`. Do not pass the Bitwarden token as text.
4. New page needs a section. Append needs a page. Do not create a second page to add a paragraph.

## Steps
1. If the section or page id is unknown, run `/onenote-list` (`tree` or `pages`) and use the printed id.
2. New page: `$N create --section "SECTION" --title "TITLE" --text "BODY" --apply`.
3. Add to a page: `$N append "TITLE_OR_ID" --text "BODY" --apply`.
4. If the script exits 10, it did not send. Re-run with `--apply` only if the user asked to save.
5. If the script prints `ERROR`, stop and report that line.

## Reply
```
Saved: <title> | <id>
Section: <section>
```
If nothing was sent: `Not sent. <the PLAN lines>`

## Gotchas
- `--text` and `--file` are plain text. The script escapes them. Tags are stored as text, not as formatting.
- A 401 that mentions Notes.ReadWrite means the saved token cannot write OneNote. Stop. Do not retry.

## Before you finish
- [ ] `--apply` was used only because the user asked to save
- [ ] the id in the reply came from `OK created` or `OK appended`
