#!/usr/bin/env python3
"""Content ideas: gather what happened (on this rig and in the niche), keep a clean idea backlog.

  ideas.py gather [--days 7]       rig activity + niche trends -> ~/content/ideas/sources-DATE.md (prints a summary)
  ideas.py add --title T --angle A --formats "x,short,video" --hook H --evidence "command or file" [--pillar P]
  ideas.py list [--status new]     the backlog, one line per idea (id, status, score, title)
  ideas.py set ID STATUS           new | planned | drafted | published | dropped
  ideas.py show ID                 one idea in full

Sources: rig change journal, git logs of the rig repos, benchmark result files (your own data = the original part);
Hugging Face trending models, r/LocalLLaMA top of the week (RSS), Hacker News (Algolia), llama.cpp releases.
"""
import argparse, datetime, html, json, pathlib, re, subprocess, sys, time, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import content  # noqa: E402

IDEAS = content.ROOT / "ideas"
BACKLOG = IDEAS / "backlog.md"
UA = "Mozilla/5.0 (X11; Linux x86_64) rig-content-ideas/1.0"
REPOS = pathlib.Path.home() / "Desktop" / "github_repos"
JOURNAL = pathlib.Path.home() / ".local/state/rig-skills/journal.log"
KEYWORDS = re.compile(r"llm|local|llama|gguf|quant|model|agent|gpu|vram|inference|qwen|gemma|deepseek|mistral|rocm|"
                      r"vllm|ollama|open.?weight|open.?source|mcp|rag|token", re.I)
STATUSES = ("new", "planned", "drafted", "published", "dropped")


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def rig_activity(days):
    out = []
    since = datetime.datetime.now() - datetime.timedelta(days=days)
    if JOURNAL.is_file():
        for line in JOURNAL.read_text().splitlines()[-300:]:
            m = re.match(r"\[(\d{4}-\d\d-\d\d) [\d:]+\] (.*)", line)
            if m and datetime.datetime.fromisoformat(m.group(1)) >= since:
                out.append(f"journal {m.group(1)}: {m.group(2)[:200]}")
    for repo in sorted(REPOS.glob("*/.git")):
        r = subprocess.run(["git", "-C", str(repo.parent), "log", f"--since={days} days ago", "--all", "--no-merges",
                            "--pretty=%ad %s", "--date=short"], capture_output=True, text=True)
        for line in r.stdout.splitlines()[:15]:
            out.append(f"{repo.parent.name}: {line[:180]}")
    for f in sorted((REPOS / "local-llm-bench-results").rglob("*.md"), key=lambda p: p.stat().st_mtime)[-5:] \
            if (REPOS / "local-llm-bench-results").is_dir() else []:
        if f.stat().st_mtime > since.timestamp():
            out.append(f"bench result file: {f}")
    return out


def trends():
    res, errs = {}, []
    try:
        models = json.loads(get("https://huggingface.co/api/models?sort=trendingScore&limit=25"))
        res["Hugging Face trending models"] = [f"{m['id']} (trend {m.get('trendingScore')}, {m.get('downloads', 0)} dl) "
                                               f"https://huggingface.co/{m['id']}" for m in models]
    except Exception as e:  # noqa: BLE001
        errs.append(f"huggingface: {e}")
    try:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(get("https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week&limit=30"))
        res["r/LocalLLaMA top this week"] = [f"{html.unescape(e.findtext('a:title', '', ns))} "
                                             f"{e.find('a:link', ns).get('href')}" for e in root.findall("a:entry", ns)]
    except Exception as e:  # noqa: BLE001
        errs.append(f"reddit: {e}")
    try:
        since = int(time.time()) - 7 * 86400
        hits = json.loads(get("https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=60"
                              f"&numericFilters=created_at_i>{since},points>60"))["hits"]
        res["Hacker News (7 days, AI/LLM)"] = [f"{h['title']} ({h['points']} pts) https://news.ycombinator.com/item?id="
                                               f"{h['objectID']}" for h in hits if KEYWORDS.search(h.get("title", ""))][:20]
    except Exception as e:  # noqa: BLE001
        errs.append(f"hn: {e}")
    try:
        rel = json.loads(get("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=30"))
        notable = []
        for r in rel:
            body = (r.get("body") or "").strip().splitlines()
            first = next((l for l in body if l.strip() and not l.startswith(("<", "#", "!"))), "")
            notable.append(f"{r['tag_name']} {r['published_at'][:10]}: {first[:140]}")
        res["llama.cpp releases (latest 30, one line each)"] = notable
    except Exception as e:  # noqa: BLE001
        errs.append(f"github: {e}")
    return res, errs


def gather(days):
    IDEAS.mkdir(parents=True, exist_ok=True)
    rig = rig_activity(days)
    tr, errs = trends()
    f = IDEAS / f"sources-{datetime.date.today()}.md"
    lines = [f"# Idea sources {datetime.date.today()} (last {days} days)", "",
             "## On my rig (the original material - every idea should use some of this)", ""]
    lines += [f"- {x}" for x in rig] or ["- (nothing logged - run an experiment first)"]
    for k, v in tr.items():
        lines += ["", f"## {k}", ""] + [f"- {x}" for x in v]
    if errs:
        lines += ["", "## Sources that failed", ""] + [f"- {e}" for e in errs]
    f.write_text("\n".join(lines) + "\n")
    print(f"sources: {f}")
    print(f"rig activity: {len(rig)} items; " + "; ".join(f"{k.split(' (')[0]}: {len(v)}" for k, v in tr.items()))
    for e in errs:
        print("WARN", e)
    open_ideas = [i for i in parse() if i["status"] in ("new", "planned")]
    print(f"backlog: {len(open_ideas)} open ideas in {BACKLOG}")


def parse():
    if not BACKLOG.is_file():
        return []
    ideas = []
    for block in re.split(r"(?m)^## ", BACKLOG.read_text())[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"(\d+) \[(\w+)\] (.*)", head.strip())
        if not m:
            continue
        fields = dict(re.findall(r"(?m)^- (\w+): (.*)$", body))
        ideas.append({"id": int(m.group(1)), "status": m.group(2), "title": m.group(3), **fields, "_raw": block})
    return ideas


def write(ideas):
    out = ["# Idea backlog (edit with ideas.py; one block per idea)", ""]
    for i in sorted(ideas, key=lambda x: x["id"]):
        out.append(f"## {i['id']} [{i['status']}] {i['title']}")
        for k in ("pillar", "angle", "formats", "hook", "evidence", "added"):
            if i.get(k):
                out.append(f"- {k}: {i[k]}")
        out.append("")
    BACKLOG.write_text("\n".join(out))


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("cmd", nargs="?")
    ap.add_argument("args", nargs="*")
    for k in ("title", "angle", "formats", "hook", "evidence", "pillar", "status"):
        ap.add_argument(f"--{k}")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    if a.cmd == "gather":
        gather(a.days)
    elif a.cmd == "add":
        missing = [k for k in ("title", "angle", "formats", "hook", "evidence") if not getattr(a, k)]
        if missing:
            sys.exit(f"ERROR missing --{' --'.join(missing)}; evidence = the command or file on the rig that proves it")
        ideas = parse()
        new = {"id": max([i["id"] for i in ideas] or [0]) + 1, "status": "new", "title": a.title, "angle": a.angle,
               "formats": a.formats, "hook": a.hook, "evidence": a.evidence, "pillar": a.pillar or "",
               "added": str(datetime.date.today())}
        dup = [i for i in ideas if i["title"].lower() == a.title.lower()]
        if dup:
            sys.exit(f"ERROR idea {dup[0]['id']} has the same title")
        write(ideas + [new])
        print(f"OK added idea {new['id']}: {a.title}")
    elif a.cmd == "list":
        for i in parse():
            if not a.status or i["status"] == a.status:
                print(f"{i['id']:>3} [{i['status']}] {i['title']}  ({i.get('formats', '')})")
    elif a.cmd == "set":
        if len(a.args) != 2 or a.args[1] not in STATUSES:
            sys.exit(f"ERROR usage: ideas.py set ID STATUS  (STATUS one of {', '.join(STATUSES)})")
        ideas = parse()
        hit = [i for i in ideas if i["id"] == int(a.args[0])]
        if not hit:
            sys.exit(f"ERROR no idea {a.args[0]} (ideas.py list)")
        hit[0]["status"] = a.args[1]
        write(ideas)
        print(f"OK idea {a.args[0]} -> {a.args[1]}")
    elif a.cmd == "show":
        hit = [i for i in parse() if i["id"] == int(a.args[0])]
        print("## " + hit[0]["_raw"] if hit else f"ERROR no idea {a.args[0]}")
    else:
        print(__doc__)
        sys.exit(0 if a.cmd in (None, "-h", "--help", "help") else 2)


if __name__ == "__main__":
    main()
