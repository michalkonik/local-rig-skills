#!/usr/bin/env python3
"""X post queue: drafts you post by hand. One file per draft in ~/content/x/queue/.

  xq.py new KIND SLUG [--idea ID] [--reply-to URL]   KIND = post | thread | reply; prints the file to fill
  xq.py fetch URL                                    text + author of a public X post (for replies and quotes)
  xq.py check FILE                                   lengths, AI-tell lint, voice match -> OK or FIX list (exit 1)
  xq.py list                                         the queue, oldest first
  xq.py posted FILE [--url URL]                      move to x/posted/ after YOU posted it

Draft file: front matter, then the post text. Thread posts are separated by a line with only "---".
"""
import argparse, datetime, json, pathlib, re, shutil, subprocess, sys, urllib.request

LIB = pathlib.Path(__file__).resolve().parents[3] / "lib"
sys.path.insert(0, str(LIB))
import content  # noqa: E402

Q = content.ROOT / "x" / "queue"
POSTED = content.ROOT / "x" / "posted"
VOICE_PY = pathlib.Path(__file__).resolve().parents[2] / "content-voice" / "scripts" / "voice.py"


def split(text):
    fm = {}
    m = re.match(r"(?s)^---\n(.*?)\n---\n(.*)$", text)
    if m:
        fm = dict(re.findall(r"(?m)^(\w+):\s*(.*)$", m.group(1)))
        text = m.group(2)
    text = re.sub(r"(?s)<!--.*?-->", "", text)          # alternative hooks are comments, not part of the post
    posts = [p.strip() for p in re.split(r"(?m)^---\s*$", text) if p.strip()]
    return fm, posts


def fetch(url):
    m = re.search(r"/status(?:es)?/(\d+)", url)
    if not m:
        sys.exit("ERROR not an X post URL (…/status/<id>)")
    req = urllib.request.Request(f"https://api.fxtwitter.com/status/{m.group(1)}", headers={"User-Agent": "rig-xq/1.0"})
    try:
        t = json.loads(urllib.request.urlopen(req, timeout=20).read())["tweet"]
    except Exception as e:  # noqa: BLE001
        sys.exit(f"ERROR could not read the post ({e}) - paste its text instead")
    a = t["author"]
    print(f"@{a['screen_name']} ({a.get('followers', '?')} followers), {t.get('created_at', '')}, "
          f"{t.get('likes', 0)} likes, {t.get('replies', 0)} replies")
    print(t["text"])
    if t.get("quote"):
        print(f"[quoting @{t['quote']['author']['screen_name']}]: {t['quote']['text'][:400]}")


def check(path):
    p = pathlib.Path(path)
    fm, posts = split(p.read_text())
    if not posts:
        sys.exit("ERROR empty draft")
    premium = content.channel().get("x_premium")
    fix = []
    for k, post in enumerate(posts, 1):
        n = content.x_length(post)
        if n > 280 and not (premium and fm.get("kind") == "post"):
            fix.append(f"post {k}: {n}/280 weighted chars - cut it")
        if fm.get("kind") == "reply" and n > 220:
            fix.append(f"reply is {n} chars - good replies are 1-3 sentences")
    if re.search(r"https?://", posts[0]) and fm.get("kind") != "reply":
        fix.append("link in the first post - put it in a reply or the last post; lead with the value")
    if fm.get("kind") == "thread" and not 3 <= len(posts) <= 12:
        fix.append(f"thread has {len(posts)} posts (aim 3-12)")
    score, tells = content.lint("\n".join(posts), x=False)
    if score > 3:
        fix += [f"AI tell: {t}" for t in tells]
    elif tells:
        print("note: " + "; ".join(tells))
    if VOICE_PY.is_file() and (content.PROFILE / "voice.json").is_file():
        r = subprocess.run([sys.executable, str(VOICE_PY), "compare", str(p)], capture_output=True, text=True)
        fix += [l[5:] for l in r.stdout.splitlines() if l.startswith("FIX ")]
    if fix:
        print(f"FIX {p.name}:")
        for f in fix:
            print(" -", f)
        sys.exit(1)
    print(f"OK {p.name}: {len(posts)} post(s), longest {max(content.x_length(x) for x in posts)} chars, "
          f"ai-tell score {score}")


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("cmd", nargs="?")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--idea")
    ap.add_argument("--reply-to")
    ap.add_argument("--url")
    a = ap.parse_args()
    Q.mkdir(parents=True, exist_ok=True)
    if a.cmd == "new":
        if len(a.args) != 2 or a.args[0] not in ("post", "thread", "reply"):
            sys.exit("ERROR usage: xq.py new post|thread|reply SLUG [--idea ID] [--reply-to URL]")
        kind, slug = a.args
        f = Q / f"{datetime.date.today()}-{kind}-{re.sub(r'[^a-z0-9-]+', '-', slug.lower())}.md"
        if f.exists():
            sys.exit(f"ERROR {f} exists")
        body = {"post": "<post text>", "thread": "<post 1: the hook + the result>\n---\n<post 2>\n---\n<post 3>",
                "reply": "<your reply>"}[kind]
        f.write_text(f"---\nkind: {kind}\nidea: {a.idea or ''}\nreply_to: {a.reply_to or ''}\n"
                     f"created: {datetime.date.today()}\n---\n{body}\n")
        print(f"OK {f}")
    elif a.cmd == "fetch":
        fetch(a.args[0])
    elif a.cmd == "check":
        check(a.args[0])
    elif a.cmd == "list":
        for f in sorted(Q.glob("*.md")):
            fm, posts = split(f.read_text())
            print(f"{f.name}  {fm.get('kind')}  {posts[0][:70].replace(chr(10), ' ') if posts else ''}")
    elif a.cmd == "posted":
        src = pathlib.Path(a.args[0])
        POSTED.mkdir(parents=True, exist_ok=True)
        text = src.read_text().replace("\n---\n", f"\nposted: {datetime.datetime.now():%Y-%m-%d %H:%M}\n"
                                       f"url: {a.url or ''}\n---\n", 1)
        (POSTED / src.name).write_text(text)
        src.unlink()
        print(f"OK moved to {POSTED / src.name}")
    else:
        print(__doc__)
        sys.exit(0 if a.cmd in (None, "-h", "--help", "help") else 2)


if __name__ == "__main__":
    main()
