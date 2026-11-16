#!/usr/bin/env python3
"""Day loop for Michał's two X accounts. Writes files. Never posts.

  xmgr.py wake [--now ISO]
  xmgr.py status [--now ISO]
  xmgr.py new reply|post local_agents|youroldpalhorse SLUG --url URL [--evidence PATH] [--now ISO]
  xmgr.py check FILE
  xmgr.py fetch URL
  xmgr.py review ID --status posted|edited|dropped|ignored --note TEXT

Dates are Europe/Warsaw. XMGR_ROOT overrides the workspace (tests only).
"""
import argparse, datetime, json, os, pathlib, re, sys, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
WEEK1 = datetime.date(2026, 11, 16)          # first Monday after profiles were set (12 Nov 2026)
FIRST_REPLY = datetime.date(2026, 11, 13)    # replies may start the morning after the profiles
ROOT = pathlib.Path(os.environ.get("XMGR_ROOT", str(pathlib.Path.home() / ".openclaw/workspace/x-manager")))
OUT = ROOT / "out"
LEDGER = OUT / "ledger.jsonl"
PEOPLE = ROOT / "people.json"
AUDIT = OUT / "audit.jsonl"
ENGAGE = OUT / "engagement.jsonl"
RULES = ROOT / "strategy" / "changelog.md"
ACCOUNTS = ("local_agents", "youroldpalhorse")
LANG = {"local_agents": "en", "youroldpalhorse": "pl"}

# Reply language by weekday: (morning 07:40, evening 18:30). From STRATEGIA.md, 12 Nov 2026.
REPLIES = {
    0: ("en", "pl"), 1: ("en", "pl"), 2: ("pl", "en"), 3: ("en", "pl"),
    4: ("pl", "en"), 5: ("light", "light"), 6: ("none", "none"),
}
# Own-post slot. Empty means none. Friday Polish is allowed only with an evidence file.
OWN = {
    0: [("youroldpalhorse", "08:00 or 19:00")],
    1: [("local_agents", "16:00-17:30")],
    2: [("youroldpalhorse", "19:00")],
    3: [("local_agents", "16:00-17:30")],
    4: [("youroldpalhorse", "only with a measurement file")],
    5: [("local_agents", "10:00-11:30")],
    6: [],
}
QUERIES = {
    "en": [
        'llama.cpp (R9700 OR gfx1201 OR ROCm OR "tensor-split" OR llama-bench)',
        '"tok/s" (llama.cpp OR "local model") (AMD OR Radeon OR 3090 OR 4090 OR "DGX Spark")',
        '"on my" (llama-server OR llama.cpp) (parallel OR speculative OR ubatch)',
        "vLLM (ROCm OR RDNA OR 7900 OR R9700)",
    ],
    "pl": [
        'Bielik (lokalnie OR llama.cpp OR GPU OR "na własnym")',
        '"na własnym serwerze" (model OR LLM OR AI)',
        "llama.cpp (polsku OR Bielik OR ROCm)",
        '"wrażliwe dane" (model OR LLM) (lokalnie OR serwerze)',
    ],
}
BANNED = (
    "delve", "landscape", "pivotal", "unlock", "supercharge", "game-changer", "game changer",
    "let's dive in", "here's the kicker", "the real story", "buckle up", "i'm excited",
    "thoughts?", "agree?", "great point", "absolutely", "as an ai",
    "warto zaznaczyć", "w dzisiejszych czasach", "rewolucja", "kluczowe jest",
    "napisz w komentarzu", "a wy co sądzicie", "dm for", "book a call",
)
MEAS = re.compile(r"tok/s|t/s|\d+\s*W\b|°C", re.I)


def now(arg):
    if arg:
        dt = datetime.datetime.fromisoformat(arg)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    return datetime.datetime.now(TZ)


def day_of(dt):
    return dt.date()


def phase(d):
    if d < FIRST_REPLY:
        return "quiet", 0, 0
    if d < WEEK1:
        return "replies-only", 0, 15
    week = (d - WEEK1).days // 7 + 1
    cap = 15 if week <= 2 else 12
    return f"week-{week}", week, cap


def own_today(d):
    if d < WEEK1:
        return []
    return list(OWN[d.weekday()])


def xlen(text):
    return len(re.sub(r"https?://\S+", "x" * 23, text))


def split_fm(text):
    m = re.match(r"(?s)^---\n(.*?)\n---\n(.*)$", text)
    if not m:
        return {}, text
    fm = dict(re.findall(r"(?m)^(\w+):\s*(.*)$", m.group(1)))
    body = re.sub(r"(?s)<!--.*?-->", "", m.group(2))
    return fm, body


def proposals(d):
    p = OUT / d.isoformat() / "proposals"
    return sorted(p.glob("*.md")) if p.is_dir() else []


def read_prop(path):
    fm, body = split_fm(path.read_text())
    fm["_path"] = str(path)
    fm["_body"] = body
    return fm


def ledger_rows():
    if not LEDGER.is_file():
        return []
    rows = []
    for line in LEDGER.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def reply_count(d):
    n = 0
    for path in proposals(d):
        fm = read_prop(path)
        if fm.get("kind") == "reply" and fm.get("status") in ("proposed", "edited", "posted"):
            n += 1
    return n


def author_count(d, author):
    author = author.lstrip("@").lower()
    n = 0
    for path in proposals(d):
        fm = read_prop(path)
        if fm.get("kind") == "reply" and fm.get("status") in ("proposed", "edited", "posted"):
            if fm.get("author", "").lstrip("@").lower() == author:
                n += 1
    return n


def open_items():
    items = []
    if not OUT.is_dir():
        return items
    for path in sorted(OUT.glob("*/proposals/*.md")):
        fm = read_prop(path)
        if fm.get("status") == "proposed":
            items.append(fm)
    return items


def link_latest(name, target):
    link = OUT / name
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target.relative_to(OUT))


def header(dt):
    d = day_of(dt)
    name, week, cap = phase(d)
    morn, eve = REPLIES[d.weekday()]
    lines = [
        f"now: {dt.strftime('%Y-%m-%d %H:%M')} Europe/Warsaw",
        f"phase: {name}",
        f"reply_cap: {cap}   replies_already: {reply_count(d)}",
        f"morning_replies: {morn} 07:40-08:10   evening_replies: {eve} 18:30-19:10",
        "own_posts: " + ("; ".join(f"@{a} {w}" for a, w in own_today(d)) or "none"),
        "accounts: @local_agents English, international, including Polish people who post the work in English | @youroldpalhorse Polish only",
        "same_person: not on both accounts in the same week",
        "manager: audit yesterday before any new draft. Say what he missed, what he did too much, and what was wrong.",
        "do_not: post, reply, like, follow, unfollow, repost, or type into the X composer",
    ]
    if d < WEEK1:
        lines.append("own_posts_locked_until: 2026-11-16 (week 1). First English pin is Tue 2026-11-17 16:30. First Polish post is Wed 2026-11-18 19:00.")
    return lines


def print_queries(lang):
    if lang in ("en", "pl"):
        print(f"queries_{lang}:")
        for q in QUERIES[lang]:
            print(f"  {q}")
    elif lang == "light":
        print("queries: one pass only, the morning language of yesterday. No new thread.")
    else:
        print("queries: none. Sunday is the three-person note, not a reply day.")


def write_skeleton(path, title, extra):
    if path.exists():
        print(f"exists: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(title + "\n\n" + extra)
    print(f"wrote: {path}")


def cmd_wake(dt):
    d = day_of(dt)
    mode = "brief" if dt.hour < 8 else "scan"
    print(f"mode: {mode}")
    for line in header(dt):
        print(line)
    OUT.mkdir(parents=True, exist_ok=True)
    daydir = OUT / d.isoformat()
    daydir.mkdir(parents=True, exist_ok=True)
    if mode == "brief":
        brief = daydir / "brief.md"
        yesterday = open_items()
        ytxt = "\n".join(f"- {it.get('id')} {it.get('kind')} @{it.get('account')} status={it.get('status')} {it.get('_path')}" for it in yesterday) or "- none"
        body = (
            "## State\nFILL from the live profiles. Counts in komunikacja-x are stale.\n\n"
            "## Still open\n" + ytxt + "\n\n"
            "Ask Michał, one line each: posted / edited / dropped, and what he changed.\n"
            "Record with: python3 ~/Desktop/github_repos/local-rig-skills/skills/x-operate/scripts/xmgr.py review ID --status posted|edited|dropped|ignored --note \"...\"\n\n"
            "## Audit\nFILL before any draft. missed / too-much / wrong / worked. NONE only if the live posts match the plan. Record each: xmgr.py audit KIND --note \"...\".\n\n"
            "## People\nFILL. At most 3 to talk to, 5 to follow, 5 to unfollow. Handle, verdict, and the post URL. No list without a post. Record: xmgr.py person.\n\n"
            "## Engagement\nFILL from the profiles you just opened. Record: xmgr.py engage.\n\n"
            "## Reply targets\nFILL. At most the cap. Skip farmers. Each names a URL.\n\n"
            "## Own post\nFILL or NONE, matching own_posts above. Evidence file required.\n\n"
            "## Plan\nNONE, or one change with a number from audit or engagement. Record: xmgr.py rule.\n\n"
            "## Do not\nNo sales. No same measurement on both accounts. No header or avatar changes. Do not follow or unfollow yourself.\n"
        )
        write_skeleton(brief, f"# Brief {d.isoformat()}", body)
        link_latest("TODAY.md", brief)
        print(f"human_file: {OUT / 'TODAY.md'}")
        print("next: open both profiles and yesterday's posts first. Record audit, people, and engagement. Then drafts.")
        print("rubric: interesting = own number or own build in the last 10 posts, and they answer a technical reply. farmer = mostly quote-tweets, tool lists, thoughts?, follow-for-follow, or no original fact in the last 10.")
    else:
        scan = daydir / f"scan-{dt.strftime('%H%M')}.md"
        body = (
            "## Audit\nFILL only if he posted off-plan since the brief. Else NONE.\n\n"
            "## Changed\nFILL or NONE.\n\n"
            "## Proposals\nFILL paths from `xmgr.py new`, or none. Skip farmers.\n"
        )
        write_skeleton(scan, f"# Scan {dt.strftime('%Y-%m-%d %H:%M')}", body)
        link_latest("NEXT.md", scan)
        print(f"human_file: {OUT / 'NEXT.md'}")
        print("next: one Latest pass. Propose only a reply or post that was not already proposed today.")
    morn, eve = REPLIES[d.weekday()]
    print_queries(morn if dt.hour < 14 else eve)
    pending = open_items()
    print(f"open_proposals: {len(pending)}")
    for it in pending[:8]:
        print(f"  {it.get('id')} {it.get('status')} {it.get('_path')}")
    print_open_people()
    print_recent_audit()


def cmd_status(dt):
    for line in header(dt):
        print(line)
    print(f"today_file: {OUT / 'TODAY.md'}")
    print(f"scan_file: {OUT / 'NEXT.md'}")
    for it in open_items():
        print(f"open: {it.get('id')} @{it.get('account')} {it.get('kind')} {it.get('_path')}")


def cmd_new(dt, kind, account, slug, url, evidence):
    d = day_of(dt)
    name, week, cap = phase(d)
    if account not in ACCOUNTS:
        sys.exit("ERROR account must be local_agents or youroldpalhorse")
    if kind not in ("reply", "post"):
        sys.exit("ERROR kind must be reply or post")
    if d < FIRST_REPLY:
        sys.exit("ERROR no drafts before 2026-11-13")
    if kind == "reply" and REPLIES[d.weekday()] == ("none", "none"):
        sys.exit("ERROR Sunday is not a reply day")
    if kind == "reply" and reply_count(d) >= cap:
        sys.exit(f"ERROR reply cap {cap} already used today")
    if kind == "post":
        allowed = [a for a, _ in own_today(d)]
        if account not in allowed:
            sys.exit(f"ERROR @{account} has no own-post slot on {d.isoformat()} ({name})")
        if not evidence or not pathlib.Path(evidence).is_file():
            sys.exit("ERROR a post needs --evidence pointing at a real file (log, note, bench)")
    author = ""
    if url:
        m = re.search(r"x\.com/([^/]+)/status/", url)
        if m:
            author = m.group(1)
    if kind == "reply" and author and author_count(d, author) >= 2:
        sys.exit(f"ERROR already 2 replies to @{author} today")
    if author:
        known = load_json(PEOPLE, {})
        row = next((v for h, v in known.items() if h.lower() == author.lower()), None)
        if row and row.get("verdict") == "farmer":
            sys.exit(f"ERROR @{author} is marked farmer. Do not draft a reply.")
    daydir = OUT / d.isoformat() / "proposals"
    daydir.mkdir(parents=True, exist_ok=True)
    n = len(list(daydir.glob("*.md"))) + 1
    pid = f"{d.isoformat()}-{n:03d}"
    path = daydir / f"{n:03d}-{slug}.md"
    ev = evidence or ""
    path.write_text(
        "---\n"
        f"id: {pid}\n"
        f"version: 1\n"
        f"kind: {kind}\n"
        f"account: {account}\n"
        f"lang: {LANG[account]}\n"
        f"status: proposed\n"
        f"url: {url or ''}\n"
        f"author: {author}\n"
        f"evidence: {ev}\n"
        f"created: {dt.isoformat(timespec='minutes')}\n"
        "---\n\n"
        "DRAFT\n\n"
        "<!-- alt: -->\n<!-- alt: -->\n\n"
        "## why\nOne sentence: why this person, why today.\n\n"
        "## evidence\nWhat the file shows. No number that is not in the file.\n"
    )
    print(f"id: {pid}")
    print(f"wrote: {path}")
    print("next: replace DRAFT, then xmgr.py check")


def cmd_check(path):
    p = pathlib.Path(path)
    fm, body = split_fm(p.read_text())
    draft = body.split("## why")[0]
    draft = re.sub(r"(?m)^<!--.*?-->\s*$", "", draft).strip()
    if not draft or draft == "DRAFT":
        sys.exit("ERROR draft is empty")
    fix = []
    n = xlen(draft)
    limit = 220 if fm.get("kind") == "reply" else 280
    if n > limit:
        fix.append(f"{n}/{limit} weighted chars")
    low = draft.lower()
    for phrase in BANNED:
        if phrase in low:
            fix.append(f"banned: {phrase}")
    if draft.count("—") > 1:
        fix.append("more than one em dash")
    if re.search(r"(?m)^#\w", draft) or re.search(r"\s#\w", draft):
        fix.append("hashtag")
    if fm.get("kind") != "reply" and re.search(r"https?://", draft.split("\n", 1)[0]):
        fix.append("link in the first line")
    if re.search(r"\b(cennik|oferta|kup|DM me|link in bio)\b", draft, re.I):
        fix.append("sales language")
    ev = fm.get("evidence", "")
    if MEAS.search(draft) and not (ev and pathlib.Path(ev).is_file()):
        fix.append("measurement word without an evidence file that exists")
    if fm.get("lang") == "en" and re.search(r"[ąćęłńóśźż]", draft, re.I):
        fix.append("Polish letters in the English draft")
    # same opening as another reply today
    opening = re.sub(r"\s+", " ", draft)[:24].casefold()
    if fm.get("kind") == "reply":
        same = 0
        for other in p.parent.glob("*.md"):
            if other.resolve() == p.resolve():
                continue
            ofm = read_prop(other)
            if ofm.get("kind") != "reply":
                continue
            od = re.sub(r"\s+", " ", ofm["_body"].split("## why")[0])[:24].casefold()
            if od and not od.startswith("draft") and od == opening:
                same += 1
        if same:
            fix.append("opening repeats another reply from today")
    if fix:
        print(f"FIX {p.name}:")
        for item in fix:
            print(" -", item)
        sys.exit(1)
    print(f"OK {p.name} ({n} chars, {fm.get('kind')}, @{fm.get('account')})")


def cmd_fetch(url):
    m = re.search(r"/status(?:es)?/(\d+)", url)
    if not m:
        sys.exit("ERROR not an X post URL")
    req = urllib.request.Request(
        f"https://api.fxtwitter.com/status/{m.group(1)}",
        headers={"User-Agent": "xmgr/1.0"},
    )
    try:
        tweet = json.loads(urllib.request.urlopen(req, timeout=20).read())["tweet"]
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"ERROR could not read the post ({exc}). Use the browser and paste the text.")
    author = tweet["author"]
    print(f"@{author['screen_name']} followers={author.get('followers', '?')} created={tweet.get('created_at', '')}")
    print(f"likes={tweet.get('likes', 0)} replies={tweet.get('replies', 0)} views={tweet.get('views', '?')}")
    print(tweet.get("text", ""))


def cmd_review(pid, status, note):
    if status not in ("posted", "edited", "dropped", "ignored"):
        sys.exit("ERROR status must be posted, edited, dropped, or ignored")
    found = None
    for path in OUT.glob("*/proposals/*.md"):
        fm, body = split_fm(path.read_text())
        if fm.get("id") == pid:
            found = path
            break
    if found is None:
        sys.exit(f"ERROR no proposal {pid}")
    text = found.read_text()
    text2 = re.sub(r"(?m)^status:\s*\S+", f"status: {status}", text, count=1)
    if text2 == text:
        sys.exit("ERROR proposal has no status line")
    ver = OUT / found.parent.name / "proposals" / "versions"
    # found is .../YYYY-MM-DD/proposals/file.md so versions sit beside it
    ver = found.parent / "versions"
    ver.mkdir(parents=True, exist_ok=True)
    snap = ver / f"{pid}-{status}.md"
    snap.write_text(text)
    note_block = f"\n\n## review\nstatus: {status}\nnote: {note or ''}\n"
    found.write_text(text2.rstrip() + note_block + "\n")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.datetime.now(TZ).isoformat(timespec="minutes"),
        "id": pid,
        "status": status,
        "note": note or "",
        "file": str(found),
    }
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"recorded: {pid} {status}")
    print(f"ledger: {LEDGER}")
    print(f"previous: {snap}")


def load_json(path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def print_open_people():
    people = load_json(PEOPLE, {})
    print("open_people:")
    n = 0
    for handle, row in sorted(people.items()):
        if row.get("suggest_status") == "open":
            print(f"  @{handle} {row.get('suggest')} {row.get('verdict')} {row.get('circle')} {row.get('seen')}")
            n += 1
    if n == 0:
        print("  none")


def print_recent_audit():
    if not AUDIT.is_file():
        print("recent_audit: none")
        return
    rows = [json.loads(line) for line in AUDIT.read_text().splitlines() if line.strip()]
    print("recent_audit:")
    if not rows:
        print("  none")
        return
    for row in rows[-5:]:
        print(f"  {row.get('ts')} {row.get('kind')} {row.get('note')}")


def cmd_audit(kind, note, account):
    if kind not in ("miss", "too-much", "wrong", "worked"):
        sys.exit("ERROR kind must be miss, too-much, wrong, or worked")
    if not note or len(note) < 20:
        sys.exit("ERROR note must say what happened, at least 20 characters")
    if account and account not in ACCOUNTS:
        sys.exit("ERROR account must be local_agents or youroldpalhorse")
    row = {
        "ts": datetime.datetime.now(TZ).isoformat(timespec="minutes"),
        "kind": kind,
        "account": account,
        "note": note,
    }
    append_jsonl(AUDIT, row)
    print(f"recorded: {kind} {account or '-'}")
    print(f"file: {AUDIT}")


def cmd_person(handle, verdict, circle, why, seen, suggest):
    handle = handle.lstrip("@").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        sys.exit("ERROR handle looks wrong")
    if verdict not in ("interesting", "farmer", "watch"):
        sys.exit("ERROR verdict must be interesting, farmer, or watch")
    if circle not in ("intl", "pl"):
        sys.exit("ERROR circle must be intl or pl")
    if suggest not in ("talk", "follow", "unfollow", "none"):
        sys.exit("ERROR suggest must be talk, follow, unfollow, or none")
    if not seen or "/status/" not in seen:
        sys.exit("ERROR --seen must be the post URL you judged them by")
    if not why or len(why) < 30:
        sys.exit("ERROR --why must name the fact you saw, at least 30 characters")
    if verdict == "farmer" and suggest == "talk":
        sys.exit("ERROR do not talk to a farmer. suggest none or unfollow")
    if circle == "pl" and suggest == "talk":
        pass
    people = load_json(PEOPLE, {})
    if suggest in ("follow", "unfollow", "talk"):
        cap = {"talk": 3, "follow": 5, "unfollow": 5}[suggest]
        open_n = sum(
            1 for h, row in people.items()
            if h.lower() != handle.lower()
            and row.get("suggest") == suggest
            and row.get("suggest_status") == "open"
        )
        if open_n >= cap:
            sys.exit(f"ERROR already {cap} open {suggest} suggestions. Close one with: person HANDLE --close")
    people[handle] = {
        "verdict": verdict,
        "circle": circle,
        "why": why,
        "seen": seen,
        "suggest": suggest,
        "suggest_status": "open" if suggest != "none" else "closed",
        "updated": datetime.datetime.now(TZ).isoformat(timespec="minutes"),
    }
    PEOPLE.parent.mkdir(parents=True, exist_ok=True)
    PEOPLE.write_text(json.dumps(people, ensure_ascii=False, indent=2) + "\n")
    where = "@local_agents" if circle == "intl" else "@youroldpalhorse"
    print(f"recorded: @{handle} {verdict} {circle} -> {where} suggest={suggest}")
    print(f"file: {PEOPLE}")


def cmd_close_person(handle):
    handle = handle.lstrip("@").strip()
    people = load_json(PEOPLE, {})
    key = next((h for h in people if h.lower() == handle.lower()), None)
    if key is None:
        sys.exit(f"ERROR no @{handle}")
    people[key]["suggest_status"] = "closed"
    people[key]["updated"] = datetime.datetime.now(TZ).isoformat(timespec="minutes")
    PEOPLE.write_text(json.dumps(people, ensure_ascii=False, indent=2) + "\n")
    print(f"closed: @{key}")


def cmd_engage(account, followers, following, views, author_replies, note):
    if account not in ACCOUNTS:
        sys.exit("ERROR account must be local_agents or youroldpalhorse")
    for name, value in (("followers", followers), ("following", following), ("views", views)):
        if value < 0:
            sys.exit(f"ERROR {name} must be >= 0")
    if author_replies not in ("yes", "no", "none"):
        sys.exit("ERROR --author-replied must be yes, no, or none")
    row = {
        "ts": datetime.datetime.now(TZ).isoformat(timespec="minutes"),
        "account": account,
        "followers": followers,
        "following": following,
        "views": views,
        "author_replied": author_replies,
        "note": note or "",
    }
    append_jsonl(ENGAGE, row)
    print(f"recorded: @{account} followers={followers} views={views} author_replied={author_replies}")
    print(f"file: {ENGAGE}")


def cmd_rule(text, because):
    if not text or len(text) < 20:
        sys.exit("ERROR the rule must say what changes, at least 20 characters")
    if not because or not re.search(r"\d", because):
        sys.exit("ERROR --because needs a count, a date, or an id")
    RULES.parent.mkdir(parents=True, exist_ok=True)
    n = 1
    if RULES.is_file():
        n = len(re.findall(r"(?m)^## R\d+", RULES.read_text())) + 1
    stamp = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    block = f"\n## R{n:03d} {stamp} proposed\n{text.strip()}\nbecause: {because.strip()}\n"
    with RULES.open("a") as fh:
        fh.write(block)
    print(f"recorded: R{n:03d} proposed, not active until Michał says keep")
    print(f"file: {RULES}")
    print("Do not edit STRATEGIA.md yourself.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("wake", "status"):
        s = sub.add_parser(name)
        s.add_argument("--now")
    n = sub.add_parser("new")
    n.add_argument("kind")
    n.add_argument("account")
    n.add_argument("slug")
    n.add_argument("--url", default="")
    n.add_argument("--evidence", default="")
    n.add_argument("--now")
    c = sub.add_parser("check")
    c.add_argument("file")
    f = sub.add_parser("fetch")
    f.add_argument("url")
    r = sub.add_parser("review")
    r.add_argument("id")
    r.add_argument("--status", required=True)
    r.add_argument("--note", default="")
    au = sub.add_parser("audit")
    au.add_argument("kind")
    au.add_argument("--note", required=True)
    au.add_argument("--account", default="")
    pe = sub.add_parser("person")
    pe.add_argument("handle")
    pe.add_argument("--verdict", default="watch")
    pe.add_argument("--circle", default="intl")
    pe.add_argument("--why", default="")
    pe.add_argument("--seen", default="")
    pe.add_argument("--suggest", default="none")
    pe.add_argument("--close", action="store_true")
    en = sub.add_parser("engage")
    en.add_argument("account")
    en.add_argument("--followers", type=int, required=True)
    en.add_argument("--following", type=int, required=True)
    en.add_argument("--views", type=int, default=0)
    en.add_argument("--author-replied", default="none")
    en.add_argument("--note", default="")
    ru = sub.add_parser("rule")
    ru.add_argument("text")
    ru.add_argument("--because", required=True)
    a = p.parse_args()
    if a.cmd == "wake":
        cmd_wake(now(a.now))
    elif a.cmd == "status":
        cmd_status(now(a.now))
    elif a.cmd == "new":
        cmd_new(now(a.now), a.kind, a.account, a.slug, a.url, a.evidence)
    elif a.cmd == "check":
        cmd_check(a.file)
    elif a.cmd == "fetch":
        cmd_fetch(a.url)
    elif a.cmd == "review":
        cmd_review(a.id, a.status, a.note)
    elif a.cmd == "audit":
        cmd_audit(a.kind, a.note, a.account)
    elif a.cmd == "person" and a.close:
        cmd_close_person(a.handle)
    elif a.cmd == "person":
        cmd_person(a.handle, a.verdict, a.circle, a.why, a.seen, a.suggest)
    elif a.cmd == "engage":
        cmd_engage(a.account, a.followers, a.following, a.views, a.author_replied, a.note)
    elif a.cmd == "rule":
        cmd_rule(a.text, a.because)


if __name__ == "__main__":
    main()
