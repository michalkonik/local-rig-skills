#!/usr/bin/env python3
"""Joplin on this rig. Uses the agent profile and the local Joplin Server sync.

Never print sync passwords. Writes do nothing unless --apply is set.
Note titles are resolved only inside the current notebook. The CLI has no search
command; `search` reads the local database after one sync.
"""
import argparse, fcntl, json, os, pathlib, re, sqlite3, subprocess, sys
from datetime import datetime
from zoneinfo import ZoneInfo

PROFILE = pathlib.Path.home() / ".config/joplin-agent"
BIN = pathlib.Path.home() / ".joplin-bin/bin/joplin"
LOCK = PROFILE / "cli.lock"


class GiveUp(SystemExit):
    pass


def say(text, code=1):
    print(text)
    raise GiveUp(code)


def joplin(*args, check=True):
    if not BIN.is_file():
        say(f"ERROR joplin CLI missing: {BIN}")
    PROFILE.mkdir(parents=True, exist_ok=True)
    LOCK.touch(mode=0o600)
    with LOCK.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proc = subprocess.run([str(BIN), "--profile", str(PROFILE), *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "joplin failed").strip().splitlines()
        say("ERROR " + (err[-1][:300] if err else "joplin failed"))
    return proc


def sync():
    proc = joplin("sync", check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        say("ERROR sync: " + (err[-1][:240] if err else "failed"))


def notebooks():
    proc = joplin("ls", "/", "-l", "-f", "json")
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        say("ERROR notebooks: joplin ls did not return JSON")
    return rows if isinstance(rows, list) else []


def notes_in(title):
    joplin("use", title)
    proc = joplin("ls", "-l", "-f", "json")
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        say("ERROR notes: joplin ls did not return JSON")
    return rows if isinstance(rows, list) else []


def cmd_notebooks(_args):
    sync()
    rows = notebooks()
    print(f"OK notebooks {len(rows)}")
    for row in rows:
        print(f"- {row.get('title')} | {row.get('id')}")
    if not rows:
        print("(none)")


def cmd_notes(args):
    sync()
    rows = notes_in(args.notebook)
    print(f"OK notes {len(rows)} notebook {args.notebook}")
    for row in rows:
        print(f"- {row.get('title')} | {row.get('id')}")
    if not rows:
        print("(none)")


def cmd_read(args):
    sync()
    joplin("use", args.notebook)
    proc = joplin("cat", args.note, check=False)
    if proc.returncode != 0 or "Cannot find" in (proc.stderr or ""):
        say(f"ERROR note not found in {args.notebook}: {args.note}")
    print(f"OK read {args.note}")
    sys.stdout.write(proc.stdout or "")
    if proc.stdout and not proc.stdout.endswith("\n"):
        print()


def cmd_search(args):
    sync()
    words = " ".join(args.query).strip()
    if not words:
        say("ERROR search words required", 2)
    db = PROFILE / "database.sqlite"
    if not db.is_file():
        say(f"ERROR database missing: {db}")
    like = "%" + words.replace("%", "") + "%"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT n.title, n.id, f.title FROM notes n "
            "LEFT JOIN folders f ON f.id = n.parent_id "
            "WHERE IFNULL(n.deleted_time,0)=0 AND (n.title LIKE ? OR n.body LIKE ?) "
            "ORDER BY n.updated_time DESC LIMIT ?",
            (like, like, max(1, min(args.top, 50))),
        ).fetchall()
    finally:
        con.close()
    print(f"OK search {len(rows)} q {words[:80]}")
    for title, nid, folder in rows:
        print(f"- {title} | {folder or '(no notebook)'} | {nid}")
    if not rows:
        print("(none)")


def read_text(args):
    if args.file:
        return pathlib.Path(args.file).read_text()
    if args.text is not None:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    say("ERROR pass --text, --file, or stdin", 2)


def ensure_notebook(title, parent):
    existing = {row.get("title") for row in notebooks()}
    if title in existing:
        return
    if parent:
        joplin("mkbook", title, "-p", parent)
    else:
        joplin("mkbook", title)


def cmd_mkbook(args):
    title = args.title.strip()
    if not title:
        say("ERROR --title required", 2)
    print(f"PLAN notebook {title}" + (f" parent {args.parent}" if args.parent else ""))
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to create the notebook.", 10)
    sync()
    ensure_notebook(title, args.parent)
    sync()
    made = [row for row in notebooks() if row.get("title") == title]
    print(f"OK notebook {title} | {made[0].get('id') if made else '?'}")


def cmd_create(args):
    title = args.title.strip()
    notebook = args.notebook.strip()
    if not title or not notebook:
        say("ERROR --notebook and --title required", 2)
    text = read_text(args)
    if len(text) > 200000:
        say("ERROR body is over 200000 characters. Split the note.", 2)
    print(f"PLAN create notebook {notebook} title {title} chars {len(text)}")
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to create the note.", 10)
    sync()
    ensure_notebook(notebook, args.parent)
    joplin("use", notebook)
    joplin("mknote", title)
    joplin("set", title, "body", text)
    sync()
    print(f"OK created {title}")


CATEGORIES = {
    "company": ("#b42318", "Company"),
    "money": ("#b54708", "Money"),
    "work": ("#175cd3", "Work"),
    "admin": ("#027a48", "Admin and health"),
}


def due_ms(deadline):
    """Return a Warsaw end-of-day timestamp, or 0 when the deadline is not a date."""
    text = deadline.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        year, month, day = (int(part) for part in text.split("-"))
        when = datetime(year, month, day, 23, 59, tzinfo=ZoneInfo("Europe/Warsaw"))
        return int(when.timestamp() * 1000)
    if text.casefold() == "now":
        today = datetime.now(ZoneInfo("Europe/Warsaw"))
        when = today.replace(hour=23, minute=59, second=0, microsecond=0)
        return int(when.timestamp() * 1000)
    return 0


def cell(text):
    return text.replace("|", "\\|").replace("\n", " ").strip()


def action_body(category, description, deadline, calendar, reminder, agent_note=""):
    _color, label = CATEGORIES[category]
    # Markdown only. Joplin shows raw HTML inside a table cell, including on the Mac.
    shown_deadline = deadline.strip()
    if shown_deadline.casefold() in {"overdue", "now"}:
        shown_deadline = f"**{shown_deadline}**"
    rows = [
        ("Category", f"**{label}**"),
        ("Description", cell(description)),
        ("Deadline", cell(shown_deadline)),
        ("Google Calendar", cell(calendar)),
        ("Reminder", cell(reminder)),
        ("Note for agent", cell(agent_note)),
    ]
    lines = ["| Field | Value |", "| --- | --- |"]
    for name, value in rows:
        lines.append(f"| {name} | {value} |")
    lines.append("")
    lines.append("Checked against Google Calendar on the day this to-do was written. Birthdays, meetings, and booked courses stay on the calendar and are not copied here.")
    return "\n".join(lines)


def cmd_todo(args):
    title = args.title.strip()
    category = args.category.strip().casefold()
    deadline = args.deadline.strip()
    calendar = args.calendar.strip()
    reminder = args.reminder.strip()
    description = read_text(args).strip()
    if category not in CATEGORIES:
        say("ERROR --category must be company, money, work, or admin", 2)
    if not title or not description or not deadline or not calendar or not reminder:
        say("ERROR a to-do needs a title, description, deadline, calendar, and reminder", 2)
    if calendar.casefold().startswith("yes") and ":" not in calendar:
        say("ERROR calendar Yes must name the calendar, for example 'Yes: primary (michal.konik.praca@gmail.com)'", 2)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline) and deadline.casefold() not in {"now", "overdue", "not set"} and not deadline.casefold().startswith("before "):
        say("ERROR --deadline must be YYYY-MM-DD, now, overdue, not set, or 'before ...'", 2)
    body = action_body(category, description, deadline, calendar, reminder, args.agent_note or "")
    print(f"PLAN todo {title} category {category} deadline {deadline} calendar {calendar} reminder {reminder}")
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to create the to-do.", 10)
    sync()
    ensure_notebook(args.notebook, None)
    joplin("use", args.notebook)
    joplin("mktodo", title)
    joplin("set", title, "body", body)
    stamp = due_ms(deadline)
    if stamp:
        joplin("set", title, "todo_due", str(stamp))
    arrange_actions()
    sync()
    print(f"OK todo {title}")


def cmd_append(args):
    text = read_text(args)
    if len(text) > 200000:
        say("ERROR body is over 200000 characters. Split the note.", 2)
    print(f"PLAN append {args.notebook} / {args.note} chars {len(text)}")
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to append.", 10)
    sync()
    joplin("use", args.notebook)
    current = joplin("cat", args.note, check=False)
    if current.returncode != 0 or "Cannot find" in (current.stderr or ""):
        say(f"ERROR note not found in {args.notebook}: {args.note}")
    body = current.stdout or ""
    # cat prints the title as the first line.
    if body.startswith(args.note + "\n"):
        body = body[len(args.note) + 1:]
    if body and not body.endswith("\n"):
        body += "\n"
    joplin("set", args.note, "body", body + text)
    sync()
    print(f"OK appended {args.note}")


# Lower rank is more important. Dated items always sort above these.
UNDATED_RANK = {
    "Get the missing wedding papers": 10,
    "Apply for the ID card online": 20,
    "Follow up on the blood tests": 30,
    "Get the Generali refund": 40,
    "Submit the RARR incubation application": 50,
    "Confirm the year on the Asia quotes": 60,
    "Finish the budget": 70,
    "Set the date to leave the second job": 80,
    "Open N26, check Lloyds, close Nest and Millennium": 90,
    "Write the recession plan": 100,
    "Send the old laptop to Warsaw": 110,
    "Check the Atlassian MCP in Ledger": 120,
}
CATEGORY_RANK = {"admin": 200, "company": 210, "money": 220, "work": 230}
def table_rows(body):
    rows = []
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if not cells or cells[0] in {"Field", "Task", "Completed"} or set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def field_map(body):
    found = {}
    for cells in table_rows(body):
        if len(cells) >= 2:
            found[cells[0]] = cells[1]
        if cells[0] == "Note for agent" and len(cells) >= 3 and cells[2].strip():
            found["Note for agent"] = cells[2]
    return found


def plain_deadline(text):
    return text.replace("**", "").strip()


def sort_key(title, deadline, category):
    low = plain_deadline(deadline).casefold()
    if low == "overdue":
        return (0, "", 0, title)
    if low == "now":
        return (1, "", 0, title)
    if low.startswith("before"):
        return (2, "", 0, title)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", low):
        pay_first = 0 if title.casefold().startswith("pay ") else 1
        return (3, low, pay_first, title)
    rank = UNDATED_RANK.get(title, CATEGORY_RANK.get(category, 500))
    return (4, "", rank, title)


def category_of(value):
    text = re.sub(r"<[^>]+>", "", value).replace("**", "")
    for key, (color, label) in CATEGORIES.items():
        if label.casefold() == text.strip().casefold():
            return key, color, label
    return "admin", CATEGORIES["admin"][0], text.strip() or "Admin and health"


def task_cell(title, nid, _label):
    # The whole cell is the link. A bold word in front of it is not clickable.
    return f"[{cell(title)}](:/{nid})"


def arrange_actions():
    """Sort open to-dos, keep the agent-note row, and file completed ones."""
    db = PROFILE / "database.sqlite"
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    folder = con.execute("select id from folders where title='Actions' and ifnull(deleted_time,0)=0").fetchone()
    if folder is None:
        con.close()
        say("ERROR notebook Actions is missing")
    notes = con.execute(
        "select id, title, body, is_todo, todo_completed, todo_due from notes "
        "where parent_id=? and ifnull(deleted_time,0)=0",
        (folder["id"],),
    ).fetchall()
    open_items = []
    done_items = []
    index = None
    completed_note = None
    for note in notes:
        if note["is_todo"]:
            (done_items if note["todo_completed"] else open_items).append(note)
        elif note["title"] == "Actions":
            index = note
        elif note["title"] == "Completed Actions":
            completed_note = note
    ranked = []
    for note in open_items:
        fields = field_map(note["body"] or "")
        deadline = plain_deadline(fields.get("Deadline", "not set"))
        category, color, label = category_of(fields.get("Category", ""))
        agent = fields.get("Note for agent", "").strip()
        ranked.append((sort_key(note["title"], deadline, category), note, fields, deadline, label, color, agent))
    ranked.sort(key=lambda item: item[0])
    now = int(datetime.now(ZoneInfo("Europe/Warsaw")).timestamp() * 1000)
    for position, item in enumerate(ranked, start=1):
        _key, note, fields, deadline, label, color, agent = item
        description = fields.get("Description", "").strip()
        calendar = fields.get("Calendar", fields.get("Google Calendar", "No")).strip() or "No"
        reminder = fields.get("Reminder", "Not set").strip() or "Not set"
        category, _color, _label = category_of(fields.get("Category", label))
        body = action_body(category, description or note["title"], deadline or "not set", calendar, reminder, agent) + "\n"
        con.execute(
            "update notes set body=?, \"order\"=?, updated_time=?, user_updated_time=? where id=?",
            (body, position * 1000, now, now, note["id"]),
        )
    # Completed page. Newest finished item first. The to-do itself is removed below.
    old_rows = []
    if completed_note is not None:
        for cells in table_rows(completed_note["body"] or ""):
            if len(cells) >= 6:
                old_rows.append(cells)
    fresh = []
    known = {cells[1] for cells in old_rows}
    for note in sorted(done_items, key=lambda item: item["todo_completed"], reverse=True):
        if note["title"] in known:
            continue
        fields = field_map(note["body"] or "")
        when = datetime.fromtimestamp(note["todo_completed"] / 1000, ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M")
        fresh.append([
            when,
            cell(note["title"]),
            cell(fields.get("Description", "").strip() or note["title"]),
            cell(plain_deadline(fields.get("Deadline", "not set")) or "not set"),
            cell(fields.get("Google Calendar", "No").strip() or "No"),
            cell(fields.get("Reminder", "Not set").strip() or "Not set"),
            cell(fields.get("Note for agent", "").strip()),
        ])
    completed_lines = [
        "Finished work stays here with the description, so it is still clear later. The to-do is removed. Write a note for the agent in the last column.",
        "",
        "| Completed | Task | Description | Deadline | Calendar | Reminder | Note for agent |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cells in fresh + old_rows:
        completed_lines.append("| " + " | ".join(cells[:7]) + " |")
    completed_body = "\n".join(completed_lines) + "\n"
    if completed_note is None:
        con.commit()
        con.close()
        joplin("use", "Actions")
        joplin("mknote", "Completed Actions")
        con = sqlite3.connect(db)
        completed_note = con.execute(
            "select id from notes where title='Completed Actions' and parent_id=? and ifnull(deleted_time,0)=0",
            (folder["id"],),
        ).fetchone()
        if completed_note is None:
            con.close()
            say("ERROR Completed Actions was not created")
        completed_id = completed_note[0]
    else:
        completed_id = completed_note["id"]
    con.execute(
        "update notes set body=?, updated_time=?, user_updated_time=? where id=?",
        (completed_body, now, now, completed_id),
    )
    # Actions index, same order as the to-do list.
    today = datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%-d %b %Y")
    index_lines = [
        "Only things to do. Soonest deadline at the top. Items with no deadline follow, most important first. Click the task name to open the to-do.",
        "",
        "Write a note for the agent on the to-do, in the row Note for agent. It is copied into the right-hand column here. On a finished item, write it in Completed Actions. A note is read and acted on.",
        "",
        f"Checked {today} against primary (`michal.konik.praca@gmail.com`), Choroby i Leki, Y, and Yana-and-Michal. None of these open tasks is on a calendar. The primary calendar has no default reminders, so a reminder is not set.",
        "",
        "Related, and not copied here: Spotkanie z ksi\u0119gow\u0105 mentzen, 26 Nov 2026 15:00, primary calendar. Its reminder is off.",
        "",
        "| Category | Task | Deadline | Calendar | Reminder | Note for agent |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    # Re-read bodies we just wrote so the index matches.
    for position, item in enumerate(ranked, start=1):
        _key, note, fields, deadline, label, color, agent = item
        calendar = fields.get("Google Calendar", "No").strip() or "No"
        reminder = fields.get("Reminder", "Not set").strip() or "Not set"
        index_lines.append(
            f"| {cell(label)} | {task_cell(note['title'], note['id'], label)} | {cell(deadline or 'not set')} | {cell(calendar)} | {cell(reminder)} | {cell(agent)} |"
        )
    if index is not None:
        con.execute(
            "update notes set body=?, \"order\"=?, updated_time=?, user_updated_time=? where id=?",
            ("\n".join(index_lines) + "\n", 0, now, now, index["id"]),
        )
    con.commit()
    con.close()
    removed = []
    for note in done_items:
        joplin("rmnote", "-f", note["id"])
        removed.append(note["title"])
    # Custom order, soonest at the top. The desktop may keep its own copy until it restarts.
    settings = pathlib.Path.home() / ".config/joplin-desktop/settings.json"
    if settings.is_file():
        data = json.loads(settings.read_text())
        data["notes.sortOrder.field"] = "order"
        data["notes.sortOrder.reverse"] = False
        settings.write_text(json.dumps(data) + "\n")
    print(f"ORDER open {len(ranked)} moved {len(removed)}")
    for position, item in enumerate(ranked, start=1):
        _key, note, _fields, deadline, _label, _color, agent = item
        suffix = f" | agent: {agent}" if agent else ""
        print(f"{position}. {deadline or 'not set'} | {note['title']}{suffix}")
    for note in done_items:
        fields = field_map(note["body"] or "")
        agent = fields.get("Note for agent", "").strip()
        if agent:
            print(f"AGENT completed | {note['title']} | {agent}")
    if removed:
        print("MOVED " + " | ".join(removed))
    return ranked


def cmd_complete(args):
    title = args.title.strip()
    if not title:
        say("ERROR --title required", 2)
    print(f"PLAN complete {title}")
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to complete the to-do.", 10)
    sync()
    db = PROFILE / "database.sqlite"
    con = sqlite3.connect(db)
    row = con.execute(
        "select n.id from notes n join folders f on f.id=n.parent_id "
        "where f.title=? and n.title=? and n.is_todo=1 and ifnull(n.deleted_time,0)=0 and ifnull(n.todo_completed,0)=0",
        (args.notebook, title),
    ).fetchone()
    con.close()
    if row is None:
        say(f"ERROR open to-do not found in {args.notebook}: {title}")
    joplin("set", row[0], "todo_completed", str(int(datetime.now(ZoneInfo("Europe/Warsaw")).timestamp() * 1000)))
    arrange_actions()
    sync()
    print(f"OK complete {title}")


def cmd_prepare(args):
    print("PLAN prepare actions")
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to sort and file completed to-dos.", 10)
    sync()
    arrange_actions()
    sync()
    print("OK prepare")


def build():
    p = argparse.ArgumentParser(prog="joplin.py", description="Joplin helper for this rig.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        return sp

    add("notebooks", cmd_notebooks)
    a = add("notes", cmd_notes)
    a.add_argument("notebook")
    a = add("read", cmd_read)
    a.add_argument("notebook")
    a.add_argument("note")
    a = add("search", cmd_search)
    a.add_argument("query", nargs="+")
    a.add_argument("--top", type=int, default=20)
    a = add("mkbook", cmd_mkbook)
    a.add_argument("--title", required=True)
    a.add_argument("--parent")
    a.add_argument("--apply", action="store_true")
    a = add("create", cmd_create)
    a.add_argument("--notebook", required=True)
    a.add_argument("--parent")
    a.add_argument("--title", required=True)
    a.add_argument("--text")
    a.add_argument("--file")
    a.add_argument("--apply", action="store_true")
    a = add("append", cmd_append)
    a.add_argument("notebook")
    a.add_argument("note")
    a.add_argument("--text")
    a.add_argument("--file")
    a.add_argument("--apply", action="store_true")
    a = add("todo", cmd_todo)
    a.add_argument("--notebook", default="Actions")
    a.add_argument("--title", required=True)
    a.add_argument("--category", required=True)
    a.add_argument("--deadline", required=True)
    a.add_argument("--calendar", required=True)
    a.add_argument("--reminder", required=True)
    a.add_argument("--text")
    a.add_argument("--file")
    a.add_argument("--agent-note", default="")
    a.add_argument("--apply", action="store_true")
    a = add("complete", cmd_complete)
    a.add_argument("--title", required=True)
    a.add_argument("--notebook", default="Actions")
    a.add_argument("--apply", action="store_true")
    a = add("prepare", cmd_prepare)
    a.add_argument("--apply", action="store_true")
    return p


def main(argv=None):
    args = build().parse_args(argv)
    try:
        args.fn(args)
    except GiveUp as exc:
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
