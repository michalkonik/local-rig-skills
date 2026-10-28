"""Shared helpers for the content skills (X posts, YouTube videos): workspace paths, channel profile, AI-tell lint.

Workspace (private, never in git): ~/content/
  profile/channel.json   handles, niche, pillars, voice for narration, colours   (created by `content.py init`)
  profile/voice.md       how the user writes - built by /content-voice from profile/samples/
  profile/samples/       the user's own posts and texts (the source of the voice)
  ideas/backlog.md       idea backlog (/content-ideas)
  x/queue/ x/posted/     drafts ready to post / posted (/write-x-post)
  videos/<slug>/         one folder per video or short (/make-youtube-video, /make-youtube-short)
  reviews/               weekly reviews (/content-weekly-review)

CLI:  python3 lib/content.py init | lint FILE [--x] [--strict] | count TEXT_OR_FILE | paths
"""
import json, math, pathlib, re, statistics, sys

HOME = pathlib.Path.home()
ROOT = HOME / "content"
PROFILE = ROOT / "profile"
CHANNEL = PROFILE / "channel.json"
VOICE = PROFILE / "voice.md"
VIDEOS = ROOT / "videos"
SPEACHES = "http://127.0.0.1:8001/v1"

DEFAULT_CHANNEL = {
    "name": "", "x_handle": "@", "youtube_handle": "@",
    "niche": "running LLMs locally and building agents on them - real hardware, real numbers",
    "pillars": ["rig experiments and benchmarks", "agent builds that run locally", "tooling and configs explained",
                "news through the lens of 'can I run it at home?'"],
    "audience": "developers and tinkerers who want frontier-ish AI on their own hardware",
    "tts_model": "speaches-ai/Kokoro-82M-v1.0-ONNX", "tts_voice": "am_michael", "tts_speed": 1.0,
    "accent": "#7cf29c", "bg": "#0d1117", "fg": "#e6edf3",
    "x_premium": False,
    "pronounce": {},
}

# Words and moves that make text read as machine-written. Kept short and concrete on purpose:
# each entry is something a careful human editor would also cut.
TELL_WORDS = [
    "delve", "delving", "tapestry", "testament", "realm", "landscape", "ever-evolving", "fast-paced", "game-changer",
    "game changer", "seamless", "seamlessly", "robust", "leverage", "leveraging", "harness", "harnessing", "unlock",
    "unleash", "elevate", "empower", "foster", "showcase", "boasts", "pivotal", "crucial", "paramount", "nuanced",
    "multifaceted", "intricate", "underscore", "underscores", "cutting-edge", "revolutionize", "revolutionary",
    "supercharge", "groundbreaking", "transformative", "embark", "navigate", "navigating", "in the world of",
    "moreover", "furthermore", "additionally", "in conclusion", "in summary", "ultimately", "notably", "arguably",
    "it's worth noting", "it is worth noting", "it's important to note", "dive into", "deep dive", "let's dive",
    "buckle up", "let that sink in", "here's the thing", "here's the kicker", "spoiler:", "the secret sauce",
    "unlock the power", "whether you're", "look no further", "in today's", "the future of", "stay tuned",
    "a must-have", "next level", "next-level", "mind-blowing", "insane", "it's a wild ride", "elevate your",
    "streamline", "synergy", "holistic", "plethora", "myriad", "vibrant", "meticulous", "meticulously",
]
TELL_PATTERNS = [
    (r"\bnot (just|only|merely) [^.!?\n]{1,60}[,;:—-]+\s*(it'?s|but|it is)\b", "'not just X, it's Y' construction"),
    (r"(?m)^(Not [^.\n]{1,40}\.\s*){2,}", "'Not X. Not Y.' staccato"),
    (r"—", "em dash (people rarely type them on X)"),
    (r"(?m)^\s*(\d+[/.)]|[-•*])\s*\*\*[^*]+\*\*:", "bold-label bullet list (reads like a generated listicle)"),
    (r"#\w+.*#\w+", "more than one hashtag"),
    (r"(?i)\b(game|world|life)[- ]chang", "'changing' hype"),
    (r"(?i)^(so|well|alright),\s", "filler opener"),
    (r"(?i)\?\s*(here'?s|the answer)", "rhetorical question + answer reveal"),
    (r"(?i)\bI (hope|trust) this (helps|finds you)", "assistant sign-off"),
    (r"(?i)\b(thrilled|excited) to (share|announce)", "announcement cliché"),
]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
URL = re.compile(r"https?://\S+")


def channel():
    if CHANNEL.is_file():
        return {**DEFAULT_CHANNEL, **json.loads(CHANNEL.read_text())}
    return dict(DEFAULT_CHANNEL)


def x_length(text):
    """X's weighted length: URLs count 23, emoji 2, CJK 2, everything else 1."""
    t = URL.sub("x" * 23, text)
    n = 0
    for ch in t:
        n += 2 if (EMOJI.match(ch) or "ᄀ" <= ch <= "ￜ") else 1
    return n


def lint(text, x=False):
    """Return (score, findings). Score 0 = clean; each finding adds weight. Findings are short strings."""
    findings, score = [], 0
    low = text.lower()
    for w in TELL_WORDS:
        for m in re.finditer(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", low):
            line = low.count("\n", 0, m.start()) + 1
            findings.append(f"L{line}: '{w}'")
            score += 2
    for pat, why in TELL_PATTERNS:
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            findings.append(f"L{line}: {why}")
            score += 2 if "em dash" not in why else 1
    emojis = len(EMOJI.findall(text))
    if emojis > 2:
        findings.append(f"{emojis} emoji (keep 0-1)")
        score += emojis - 2
    sents = [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.split()) >= 3]
    if len(sents) >= 5:
        lens = [len(s.split()) for s in sents]
        cv = statistics.pstdev(lens) / max(1, statistics.mean(lens))
        if cv < 0.35:
            findings.append(f"sentence lengths too uniform (cv {cv:.2f}, aim > 0.45): mix short and long")
            score += 3
    if not re.search(r"\d", text):
        findings.append("no number anywhere - add the measured value, version, price or date")
        score += 2
    if x:
        n = x_length(text.split("\n---\n")[0])
        if n > 280:
            findings.append(f"first post is {n} weighted chars (> 280; fine only with X Premium long posts)")
    return score, findings


def init():
    for d in ("profile/samples", "ideas", "x/queue", "x/posted", "videos", "reviews"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    if not CHANNEL.is_file():
        CHANNEL.write_text(json.dumps(DEFAULT_CHANNEL, indent=2) + "\n")
    print(f"workspace {ROOT} ready; edit {CHANNEL} (handles, voice); put your own writing in {PROFILE/'samples'}/")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "paths":
        print(__doc__.split("CLI:")[0].strip())
    elif a[0] == "init":
        init()
    elif a[0] == "count":
        src = a[1]
        t = pathlib.Path(src).read_text() if pathlib.Path(src).is_file() else src
        print(x_length(t))
    elif a[0] == "lint":
        t = pathlib.Path(a[1]).read_text() if a[1] != "-" else sys.stdin.read()
        t = re.sub(r"(?s)^---\n.*?\n---\n", "", t)          # skip front matter
        score, f = lint(t, x="--x" in a)
        limit = 0 if "--strict" in a else 3
        print(f"ai-tell score {score} ({'PASS' if score <= limit else 'FIX'}, limit {limit})")
        for line in f:
            print(" -", line)
        sys.exit(0 if score <= limit else 1)
    else:
        print(__doc__)
        sys.exit(2)
