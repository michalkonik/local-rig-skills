#!/usr/bin/env python3
"""Weekly numbers from your own analytics exports -> a review file with the facts filled in.

  review.py run [--week 2026-W44]   read every CSV in ~/content/reviews/inbox/, write ~/content/reviews/WEEK.md
  review.py columns FILE            show how a CSV's columns were understood (debug a new export format)

Exports to drop into the inbox (by hand, no API needed):
  X: analytics.x.com -> Content (posts) -> Export data (CSV).
  YouTube: Studio -> Analytics -> Advanced mode -> Content (videos) -> Export current view -> Comma-separated values
  (the 'Table data.csv' inside the zip).
Posts are matched to your queue files (x/posted/) by text, so each row gets its kind (post/thread/reply) and idea.
"""
import csv, datetime, pathlib, re, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import content  # noqa: E402

INBOX = content.ROOT / "reviews" / "inbox"
FIELDS = {  # canonical name: substrings that identify the column (lower case)
    "text": ["post text", "tweet text", "text"], "title": ["video title", "title"], "date": ["date", "time", "publish"],
    "impressions": ["impressions"], "engagements": ["engagements"], "likes": ["likes"], "replies": ["replies"],
    "reposts": ["reposts", "retweets"], "bookmarks": ["bookmarks"], "profile_visits": ["profile visits", "profile clicks"],
    "follows": ["follows", "new follows"], "views": ["views"], "watch_hours": ["watch time (hours)", "watch time"],
    "ctr": ["click-through rate"], "avd": ["average view duration"], "subs": ["subscribers"],
    "avg_pct": ["average percentage viewed"], "id": ["post id", "tweet id", "content", "video"],
}


def colmap(header):
    low = [h.strip().lower() for h in header]
    m = {}
    for name, keys in FIELDS.items():
        for k in keys:
            hit = next((i for i, h in enumerate(low) if k in h and i not in m.values()), None)
            if hit is not None:
                m[name] = hit
                break
    return m


def num(v):
    v = (v or "").replace(",", "").replace("%", "").strip()
    if re.fullmatch(r"\d+:\d\d(:\d\d)?", v):
        p = [int(x) for x in v.split(":")]
        return p[0] * 60 + p[1] if len(p) == 2 else p[0] * 3600 + p[1] * 60 + p[2]
    try:
        return float(v)
    except ValueError:
        return None


def load(f):
    with open(f, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return None, []
    m = colmap(rows[0])
    kind = "youtube" if "watch_hours" in m or "title" in m and "views" in m else "x" if "impressions" in m else "?"
    out = []
    for r in rows[1:]:
        if not any(r) or (r[0].strip().lower() == "total"):
            continue
        d = {k: (r[i] if i < len(r) else "") for k, i in m.items()}
        out.append(d)
    return kind, out


def posted_index():
    idx = []
    for f in (content.ROOT / "x" / "posted").glob("*.md"):
        t = f.read_text()
        fm = dict(re.findall(r"(?m)^(\w+):\s*(.*)$", t.split("\n---\n", 1)[0]))
        body = t.split("\n---\n", 1)[-1]
        idx.append((re.sub(r"\W+", " ", body.lower())[:80], fm.get("kind", ""), fm.get("idea", "")))
    return idx


def tag(text, idx):
    key = re.sub(r"\W+", " ", (text or "").lower())[:60]
    for k, kind, idea in idx:
        if key and key[:40] in k:
            return kind, idea
    return "", ""


def x_section(rows):
    idx = posted_index()
    for r in rows:
        r["impr"] = num(r.get("impressions")) or 0
        r["eng"] = num(r.get("engagements")) or sum(num(r.get(k)) or 0 for k in ("likes", "replies", "reposts", "bookmarks"))
        r["rate"] = r["eng"] / r["impr"] if r["impr"] else 0
        r["kind"], r["idea"] = tag(r.get("text"), idx)
    if not rows:
        return ["(no X rows)"]
    med = statistics.median(r["impr"] for r in rows)
    lines = [f"- posts: {len(rows)}, median impressions {med:.0f}, total impressions {sum(r['impr'] for r in rows):.0f}, "
             f"engagement rate median {statistics.median(r['rate'] for r in rows):.2%}",
             f"- follows from posts: {sum(num(r.get('follows')) or 0 for r in rows):.0f}, profile visits: "
             f"{sum(num(r.get('profile_visits')) or 0 for r in rows):.0f}", "", "Top 5 by impressions:"]
    fmt = lambda r: f"  - {r['impr']:.0f} impr, {r['rate']:.1%} eng, {r['kind'] or '?'}: {(r.get('text') or '')[:90]!r}"
    lines += [fmt(r) for r in sorted(rows, key=lambda r: -r["impr"])[:5]]
    lines += ["", "Bottom 5 by impressions:"] + [fmt(r) for r in sorted(rows, key=lambda r: r["impr"])[:5]]
    kinds = {}
    for r in rows:
        kinds.setdefault(r["kind"] or "unmatched", []).append(r["impr"])
    lines += ["", "By kind (median impressions): " + ", ".join(f"{k} {statistics.median(v):.0f} (n={len(v)})"
                                                               for k, v in kinds.items())]
    return lines


def yt_section(rows):
    if not rows:
        return ["(no YouTube rows)"]
    for r in rows:
        r["v"] = num(r.get("views")) or 0
    lines = [f"- videos: {len(rows)}, views {sum(r['v'] for r in rows):.0f}, watch hours "
             f"{sum(num(r.get('watch_hours')) or 0 for r in rows):.1f}, subscribers "
             f"{sum(num(r.get('subs')) or 0 for r in rows):+.0f}", "", "Per video (views, CTR, avg view duration, % viewed):"]
    for r in sorted(rows, key=lambda r: -r["v"])[:10]:
        avd = num(r.get("avd"))
        lines.append(f"  - {r['v']:.0f} views, CTR {r.get('ctr') or '?'}%, AVD "
                     f"{f'{int(avd//60)}:{int(avd%60):02d}' if avd else '?'}, {r.get('avg_pct') or '?'}%: "
                     f"{(r.get('title') or r.get('id') or '')[:80]}")
    return lines


def run(week):
    files = sorted(INBOX.glob("*.csv"))
    if not files:
        sys.exit(f"ERROR no CSV files in {INBOX} - export them first (see review.py --help)")
    x_rows, yt_rows, notes = [], [], []
    for f in files:
        kind, rows = load(f)
        notes.append(f"{f.name}: {kind}, {len(rows)} rows")
        (x_rows if kind == "x" else yt_rows if kind == "youtube" else []).extend(rows)
    out = content.ROOT / "reviews" / f"{week}.md"
    text = [f"# Weekly review {week}", "", "Inputs: " + "; ".join(notes), "", "## X", ""] + x_section(x_rows) + \
           ["", "## YouTube", ""] + yt_section(yt_rows) + \
           ["", "## What worked (3 bullets, with the number that shows it)", "", "## What did not", "",
            "## One experiment for next week (hypothesis, what changes, how we measure)", "",
            "## Next week's plan (posts, videos, replies per day)", ""]
    out.write_text("\n".join(text) + "\n")
    done = INBOX / "done" / week
    done.mkdir(parents=True, exist_ok=True)
    for f in files:
        f.rename(done / f.name)
    print(f"OK {out}  ({len(x_rows)} X rows, {len(yt_rows)} YouTube rows; CSVs moved to {done})")
    print("\n".join(text[4:4 + 14]))


if __name__ == "__main__":
    a = sys.argv[1:]
    INBOX.mkdir(parents=True, exist_ok=True)
    if a[:1] == ["run"]:
        wk = a[a.index("--week") + 1] if "--week" in a else datetime.date.today().strftime("%G-W%V")
        run(wk)
    elif a[:1] == ["columns"] and len(a) == 2:
        with open(a[1], newline="", encoding="utf-8-sig") as fh:
            h = next(csv.reader(fh))
        m = colmap(h)
        for k, i in m.items():
            print(f"{k:15} <- {h[i]}")
        print("unmapped:", [x for i, x in enumerate(h) if i not in m.values()])
    else:
        print(__doc__)
        sys.exit(0 if not a or a[0] in ("-h", "--help") else 2)
