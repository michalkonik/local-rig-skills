#!/usr/bin/env python3
"""Measure how the user writes, so drafts can be checked against it.

  voice.py stats            read ~/content/profile/samples/* -> voice.json (numbers) + a summary to put in voice.md
  voice.py compare FILE     how far a draft is from those numbers -> OK or "FIX ..." lines
  voice.py examples [N]     N short real sample passages (default 8) to quote in voice.md

Samples: plain .txt/.md files with the user's own writing (posts, chat messages, notes, e-mails). Blank line between
pieces. 2,000+ words gives stable numbers. Never put someone else's writing there.
"""
import collections, json, pathlib, random, re, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import content  # noqa: E402

SAMPLES = content.PROFILE / "samples"
OUT = content.PROFILE / "voice.json"


def pieces():
    out = []
    for f in sorted(SAMPLES.glob("*")):
        if f.suffix.lower() in (".txt", ".md"):
            out += [p.strip() for p in re.split(r"\n\s*\n", f.read_text(errors="replace")) if len(p.split()) >= 4]
    return out


def measure(texts):
    joined = "\n".join(texts)
    words = re.findall(r"[A-Za-z']+", joined)
    sents = [s for s in re.split(r"(?<=[.!?])\s+|\n+", joined) if len(s.split()) >= 2]
    lens = [len(s.split()) for s in sents] or [0]
    n = max(1, len(texts))
    starts = collections.Counter(s.split()[0].lower().strip(",.") for s in sents if s.split())
    return {
        "pieces": len(texts), "words": len(words),
        "sentence_words_median": statistics.median(lens),
        "sentence_words_cv": round(statistics.pstdev(lens) / max(1, statistics.mean(lens)), 2),
        "lowercase_start_rate": round(sum(1 for t in texts if t[:1].islower()) / n, 2),
        "question_rate": round(joined.count("?") / max(1, len(sents)), 2),
        "exclaim_rate": round(joined.count("!") / max(1, len(sents)), 2),
        "emoji_per_piece": round(len(content.EMOJI.findall(joined)) / n, 2),
        "em_dash_per_piece": round(joined.count("—") / n, 2),
        "hashtags_per_piece": round(len(re.findall(r"#\w", joined)) / n, 2),
        "i_rate": round(sum(1 for w in words if w.lower() in ("i", "i'm", "i've", "my", "me")) / max(1, len(words)), 3),
        "numbers_per_piece": round(len(re.findall(r"\d+", joined)) / n, 2),
        "top_openers": [w for w, _ in starts.most_common(8)],
    }


def stats():
    t = pieces()
    if not t:
        sys.exit(f"ERROR no samples in {SAMPLES} - add the user's own posts/messages as .txt or .md files")
    m = measure(t)
    OUT.write_text(json.dumps(m, indent=1))
    print(f"OK {OUT} ({m['pieces']} pieces, {m['words']} words{', THIN: add more' if m['words'] < 1500 else ''})")
    for k, v in m.items():
        if k not in ("pieces", "words"):
            print(f"  {k}: {v}")


def compare(path):
    if not OUT.is_file():
        sys.exit("ERROR no voice.json - run voice.py stats first")
    ref = json.loads(OUT.read_text())
    text = re.sub(r"(?s)^---\n.*?\n---\n", "", pathlib.Path(path).read_text())
    parts = [p.strip() for p in re.split(r"(?m)^---\s*$", text) if p.strip()]
    d = measure(parts)
    fix = []
    if d["em_dash_per_piece"] > ref["em_dash_per_piece"] + 0.2:
        fix.append("uses em dashes - you do not; use a comma, a full stop or brackets")
    if d["emoji_per_piece"] > ref["emoji_per_piece"] + 0.5:
        fix.append(f"{d['emoji_per_piece']} emoji per post, you use {ref['emoji_per_piece']}")
    if d["hashtags_per_piece"] > ref["hashtags_per_piece"] + 0.3:
        fix.append("more hashtags than you use")
    if d["exclaim_rate"] > ref["exclaim_rate"] + 0.15:
        fix.append("more exclamation marks than you use")
    if ref["lowercase_start_rate"] > 0.6 and d["lowercase_start_rate"] < 0.3:
        fix.append("you usually start posts in lowercase")
    if d["words"] > 25 and abs(d["sentence_words_median"] - ref["sentence_words_median"]) > max(4, ref["sentence_words_median"] * 0.5):
        fix.append(f"sentence length {d['sentence_words_median']} words (yours: {ref['sentence_words_median']})")
    for f in fix:
        print("FIX", f)
    if not fix:
        print("OK matches the measured voice")


def examples(n):
    t = [p for p in pieces() if 12 <= len(p.split()) <= 80]
    random.seed(7)
    for p in random.sample(t, min(n, len(t))):
        print("> " + p.replace("\n", " ")[:400] + "\n")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["stats"]:
        stats()
    elif a[:1] == ["compare"] and len(a) == 2:
        compare(a[1])
    elif a[:1] == ["examples"]:
        examples(int(a[1]) if len(a) > 1 else 8)
    else:
        print(__doc__)
        sys.exit(0 if not a or a[0] in ("-h", "--help") else 2)
