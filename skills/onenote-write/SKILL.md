---
name: onenote-write
description: Use when the user wants a new OneNote page or text added to an existing page ("save this to OneNote", "append to the note"). Action lists go out as a colored HTML table. Sends only with --apply. Not for reading - use /onenote-read. Input - section or page, title, and the text.
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
2. New plain page: `$N create --section "SECTION" --title "TITLE" --text "BODY" --apply`.
3. An action list or any comparison: write an HTML fragment to a file and `$N create --section "SECTION" --title "TITLE" --html --file FILE --apply`. Each cell is `<td style="background-color:#f4c7c3"><p>text</p></td>`. Urgent `#f4c7c3`, not urgent `#fff2cc`, long term `#cfe2f3`. Reminder off uses `<p style="color:#990000">off</p>`.
4. Add to a page: `$N append "TITLE_OR_ID" --text "BODY" --apply`.
5. If the script exits 10, it did not send. Re-run with `--apply` only if the user asked to save.
6. If the script prints `ERROR`, stop and report that line.

## Reply
```
Saved: <title> | <id>
Section: <section>
```
If nothing was sent: `Not sent. <the PLAN lines>`

## Gotchas
- Without `--html`, `--text` and `--file` are escaped. Tags show up as text.
- `--html` is a fragment inside the page body. Use `table`, `p`, and `span` only. OneNote keeps `color` and `background-color`.
- A personal account cannot move a page (`copyToSection` returns 501) and cannot indent a real sub-page. Create the new page named `Parent / Child` and leave the old page until the user approves deletion.
- A 401 means the token expired. Stop. Do not retry.

## Before you finish
- [ ] `--apply` was used only because the user asked to save
- [ ] the id in the reply came from `OK created` or `OK appended`
