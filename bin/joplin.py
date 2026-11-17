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


def action_body(category, description, deadline, calendar, reminder):
    color, label = CATEGORIES[category]
    # Markdown table. A raw HTML note shows the tags in the editor and a warning
    # banner in the viewer. The category color is the only HTML span.
    shown_deadline = deadline.strip()
    if shown_deadline.casefold() in {"overdue", "now"}:
        shown_deadline = f"**{shown_deadline}**"
    rows = [
        ("Category", f'<span style="color:{color}"><b>{label}</b></span>'),
        ("Description", cell(description)),
        ("Deadline", cell(shown_deadline)),
        ("Google Calendar", cell(calendar)),
        ("Reminder", cell(reminder)),
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
    body = action_body(category, description, deadline, calendar, reminder)
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
