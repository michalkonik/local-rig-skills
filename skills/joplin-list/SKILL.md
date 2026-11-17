---
name: joplin-list
description: Use when the user wants the Joplin notebook tree or the notes in one notebook ("show my notebooks", "what's in Inbox"). Not for note text - use /joplin-read. Not for saving - use /joplin-write. Input - optional notebook name.
---
# /joplin-list
**Goal:** list notebooks, or the notes inside one notebook.
**Output:** lines `OK ...` then `- title | id`.
`J="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/joplin.py"`

## Rules
1. Do not read `~/.config/joplin-server/secrets.env` or print a sync password.
2. Do not open `~/.config/joplin-desktop` while the Joplin app is running. The script uses the agent profile.
3. Copy ids from the script output. Do not invent them.

## Steps
1. Notebooks: `$J notebooks`.
2. Notes in one notebook: `$J notes "NOTEBOOK"`.
3. If the script prints `ERROR`, stop and report that line.

## Reply
```
Notebooks: <count>
- <title> | <id>
```
For one notebook, say `Notes in <notebook>: <count>` and list `- title | id`.

## Gotchas
- Titles are only unique inside one notebook. The same title can exist in two notebooks.
- To-dos in Actions are listed by `notes "Actions"`. Open one with `/joplin-read`.
- The script syncs before it lists. A note created on the Mac can take one sync cycle to appear.

## Before you finish
- [ ] every id in the reply came from the script
- [ ] an ERROR line was quoted, not paraphrased into a success
