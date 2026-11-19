---
name: joplin-actions
description: Use when adding, completing, sorting, or checking a Joplin action item ("add a task", "to-do", "deadline", "note for agent"). Not for ordinary notes - use /joplin-write. Not for reading one note - use /joplin-read.
---
# /joplin-actions
**Goal:** keep Actions as to-dos sorted by deadline, with a note for the agent, and move finished ones to Completed Actions.
**Output:** `OK todo`, `OK complete`, or `OK prepare`. Without `--apply` nothing is written.
`J="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/joplin.py"`

## Rules
1. Use a to-do only through this command. It stores the description, deadline, Google Calendar line, reminder line, and Note for agent. It sets the due date when the deadline is a real day.
2. Do not create a to-do when description, deadline, calendar, or reminder is unknown. Ask, or keep it as a normal note with `/joplin-write`. Note for agent may be empty.
3. Check Google Calendar before writing the calendar and reminder lines. `No` and `Not set` are valid. Do not invent a date or a reminder.
4. Do not read `~/.config/joplin-server/secrets.env` or print a sync password.
5. Open to-dos stay in deadline order, soonest at the top: overdue, now, before, then `YYYY-MM-DD`. Same day: payments before other items. No deadline: most important first (health and papers that expire, then identity, money owed, company applications, planning, convenience).
6. A finished to-do is removed. Its description is kept on the note Completed Actions.
7. Read Note for agent on open to-dos and on Completed Actions. If the cell has text, do what it asks, then write `Done: <one line>` or clear it.

## Steps
1. If the calendar status is unknown, read the calendars with `python3 ~/.openclaw/workspace/team-coordinator/scripts/gcal.py events --all 40` and the reminder fields (`useDefault`, `overrides`, calendar `defaultReminders`). A reminder is on only when overrides is non-empty, or useDefault is true and defaultReminders is non-empty.
2. `$J todo --notebook "Actions" --category company --title "TITLE" --deadline YYYY-MM-DD --calendar "No" --reminder "Not set" --agent-note "" --text "DESCRIPTION with [label](url)" --apply`
3. Category is `company`, `money`, `work`, or `admin`. Deadline is `YYYY-MM-DD`, `now`, `overdue`, `not set`, or `before ...`.
4. Calendar `Yes` must name the calendar: `Yes: primary (michal.konik.praca@gmail.com)`.
5. Finish one: `$J complete --title "TITLE" --apply`. This files the description on Completed Actions and deletes the to-do.
6. Sort, file anything already checked off, and refresh the Actions list: `$J prepare --apply`.
7. If the script prints `ERROR` or exits 10, stop. Exit 10 means it was not written.

## Reply
```
Saved to-do: <title>
Deadline: <deadline>
Calendar: <calendar>
Reminder: <reminder>
```
After prepare, list the open items in the printed order. Mention any AGENT line and what you did with it.

## Gotchas
- Joplin's own alarm is not a separate field the script can set. The reminder line records the Google Calendar reminder. Say `Not set` when there is none.
- The to-do body is a Markdown table. Do not put HTML in a table. Joplin shows the tags as text, including on the Mac.
- Meetings, birthdays, and booked courses stay on Google Calendar. Do not copy them into Actions.
- Note for agent is the last row of the to-do and the right-hand column of the Actions list. The same column is on Completed Actions.
- The 6:00 Europe/Warsaw check runs `prepare --apply`, acts on every Note for agent, and leaves a short list before 7:00.

## Before you finish
- [ ] description, deadline, calendar, and reminder were all passed
- [ ] `--apply` was used only because the user asked to save
- [ ] the reply matches `OK todo`
