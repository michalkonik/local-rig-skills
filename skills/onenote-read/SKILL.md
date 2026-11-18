---
name: onenote-read
description: Use when the user wants the text of an OneNote page or a search ("read this note", "find notes about taxes"). Not for the notebook tree - use /onenote-list. Not for saving - use /onenote-write. Input - page title, id, or the search words.
---
# /onenote-read
**Goal:** return the text of one page, or the matching titles when the page is not known yet.
**Output:** `OK read` plus the text, or `OK search` plus titles and ids.
`N="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/onenote.py"`

## Rules
1. Do not run `bw-secret` yourself. The script reads item `onenote` field `access_token`.
2. Search first when the user gave words and no page id.
3. Quote the page text from the script. Do not fill gaps from memory.

## Steps
1. Unknown page: `$N search WORDS`.
2. Known title or id: `$N read "TITLE_OR_ID"`.
3. If the script prints `OK file <path>`, read that file for the rest of the text.
4. If the script prints `ERROR`, stop and report that line.

## Reply
```
<title> | <id>
<text>
```
For a search with several hits, list `- title | id` and read a page only if the user named one.

## Gotchas
- Long pages are truncated on screen and saved under `~/.local/state/rig-skills/onenote/`.
- A page id contains `!` and is opened directly. A title is found one section at a time. Do not call `GET /me/onenote/pages`: this account returns `400 20266` (too many sections).
- A 401 means the saved token expired or was rejected. Graph Explorer tokens last about an hour. Stop and ask for a new one. Do not retry with a different token you invented.
- `40001` inside Graph Explorer, while the same token works in a direct call, means Explorer did not attach the token. Copy it again after a query that returns 200.

## Before you finish
- [ ] the text is from `read` or the saved file, not guessed
- [ ] an ERROR line was quoted, not paraphrased into a success
