---
name: joplin-write
description: Use when the user wants a Joplin notebook or note created, or text added to a note ("save this to Joplin", "append to the note"). Sends only with --apply. Not for reading - use /joplin-read. Input - notebook, title, and the text.
---
# /joplin-write
**Goal:** create a notebook or a note, or append text to an existing note.
**Output:** `OK notebook`, `OK created`, or `OK appended`. Without `--apply` nothing is written.
`J="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/joplin.py"`

## Rules
1. Do not read `~/.config/joplin-server/secrets.env` or print a sync password.
2. Add `--apply` only when the user asked to save, create, or append. A preview stays without it.
3. Put the note body in `--text` or `--file`. Do not pass a token or password as the body.
4. Append needs an existing note in that notebook. Do not create a second note to add a paragraph.
5. An action item with a deadline goes to `/joplin-actions`, not this skill. This skill is for notes.

## Steps
1. If the notebook name is unknown, run `/joplin-list` and use the printed title.
2. New notebook: `$J mkbook --title "TITLE" --apply`. Under another notebook, add `--parent "PARENT"`.
3. New note: `$J create --notebook "NOTEBOOK" --title "TITLE" --text "BODY" --apply`. Use a Markdown table when the note is a list of rows, and `<span style="color:#b42318">` only for a status word.
4. Add to a note: `$J append "NOTEBOOK" "TITLE" --text "BODY" --apply`.
5. If the script exits 10, it did not write. Re-run with `--apply` only if the user asked to save.
6. If the script prints `ERROR`, stop and report that line.

## Reply
```
Saved: <title>
Notebook: <notebook>
```
If nothing was written: `Not sent. <the PLAN line>`

## Gotchas
- `--text` and `--file` are plain Markdown. The script does not render HTML.
- A body over 200000 characters is rejected. Split it.
- The desktop app syncs on its own timer. A new note can take a few minutes to show on the Mac.

## Before you finish
- [ ] `--apply` was used only because the user asked to save
- [ ] the reply matches `OK created`, `OK appended`, or `OK notebook`
