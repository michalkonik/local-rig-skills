---
name: joplin-actions
description: Use when adding or updating a Joplin action item ("add a task", "to-do", "deadline"). Not for ordinary notes - use /joplin-write. Not for reading a note - use /joplin-read. Input - title, description, deadline, calendar, reminder.
---
# /joplin-actions
**Goal:** save one action item as a Joplin to-do with a description, links, deadline, calendar, and reminder.
**Output:** `OK todo` and the title. Without `--apply` nothing is written.
`J="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/joplin.py"`

## Rules
1. Use a to-do only through this command. It stores the description, deadline, Google Calendar line, and reminder line in the to-do body, and sets the due date when the deadline is a real day.
2. Do not create a to-do when any of those four fields is unknown. Ask, or keep it as a normal note with `/joplin-write`.
3. Check Google Calendar before writing the calendar and reminder lines. `No` and `Not set` are valid. Do not invent a date or a reminder.
4. Do not read `~/.config/joplin-server/secrets.env` or print a sync password.

## Steps
1. If the calendar status is unknown, read the calendars with `python3 ~/.openclaw/workspace/team-coordinator/scripts/gcal.py events --all 40` and the reminder fields (`useDefault`, `overrides`, calendar `defaultReminders`). A reminder is on only when overrides is non-empty, or useDefault is true and defaultReminders is non-empty.
2. `$J todo --notebook "Actions" --category company --title "TITLE" --deadline YYYY-MM-DD --calendar "No" --reminder "Not set" --text "DESCRIPTION with [label](url)" --apply`
3. Category is `company`, `money`, `work`, or `admin`. Deadline is `YYYY-MM-DD`, `now`, `overdue`, `not set`, or `before ...`.
4. Calendar `Yes` must name the calendar: `Yes: primary (michal.konik.praca@gmail.com)`.
5. If the script prints `ERROR` or exits 10, stop. Exit 10 means it was not written.

## Reply
```
Saved to-do: <title>
Deadline: <deadline>
Calendar: <calendar>
Reminder: <reminder>
```

## Gotchas
- Joplin's own alarm is not a separate field the script can set. The reminder line records the Google Calendar reminder. Say `Not set` when there is none.
- Meetings, birthdays, and booked courses stay on Google Calendar. Do not copy them into Actions.

## Before you finish
- [ ] description, deadline, calendar, and reminder were all passed
- [ ] `--apply` was used only because the user asked to save
- [ ] the reply matches `OK todo`
