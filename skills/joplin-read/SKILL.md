---
name: joplin-read
description: Use when the user wants the text of a Joplin note or a search ("read this note", "find notes about taxes"). Not for the notebook tree - use /joplin-list. Not for saving - use /joplin-write. Input - notebook plus title, or the search words.
---
# /joplin-read
**Goal:** return one note's text, or the matching titles when the note is not known yet.
**Output:** `OK read` plus the text, or `OK search` plus title, notebook, and id.
`J="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/joplin.py"`

## Rules
1. Do not read `~/.config/joplin-server/secrets.env` or print a sync password.
2. Search first when the user gave words and no notebook.
3. Quote the note text from the script. Do not fill gaps from memory.

## Steps
1. Unknown note: `$J search WORDS`.
2. Known notebook and title (or id): `$J read "NOTEBOOK" "TITLE_OR_ID"`.
3. If the script prints `ERROR`, stop and report that line.

## Reply
```
<title> | <notebook>
<text>
```
For a search with several hits, list `- title | notebook | id` and read a note only if the user named one.

## Gotchas
- `read` looks only inside the named notebook. A title that exists in another notebook is not a match.
- The CLI has no search command. `search` reads the agent database after one sync.

## Before you finish
- [ ] the text is from `read`, not guessed
- [ ] an ERROR line was quoted, not paraphrased into a success
