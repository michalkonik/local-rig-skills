#!/usr/bin/env python3
"""Full transcript of a YouTube video as Markdown: captions first, local Whisper (Speaches) when there are none.

  yt_transcript.py "<URL or search phrase>" [--lang xx] [--whisper] [--out DIR] [--basename NAME] [--library] [--chunk-min 10] [--pick-only]

  --lang xx      wanted language (default: the video's original language)
  --whisper      skip captions, transcribe the audio with Speaches (also the automatic fallback)
  --pick-only    only resolve the video and print title/channel (check a search pick before the long work)
  --out DIR      default ~/Documents/transcripts
  --basename     file name inside --out (default <upload-date>-<slug>.md)
  --library      write transcript.md into ~/Desktop/github_repos/videos-transcriptions, grouped by channel

Writes the Markdown file and prints a short summary (path, source, language, words). The file has the title
block (including video id and channel id), timestamped paragraphs, and a Description section with the
uploader's text. yt-dlp lives in its own venv (~/.local/share/rig-skills/venvs/yt-dlp, pinned); it is created
on first use.
"""
import argparse, datetime, html, json, pathlib, re, shutil, subprocess, sys, tempfile, time, urllib.request, uuid

VENV = pathlib.Path.home() / ".local/share/rig-skills/venvs/yt-dlp"
YTDLP_PIN = "yt-dlp[default]==2026.8.19"      # pinned stable release (>= 2 weeks old when chosen)
YTDLP = VENV / "bin/yt-dlp"
SPEACHES = "http://127.0.0.1:8001/v1"
WHISPER = "deepdml/faster-whisper-large-v3-turbo-ct2"
PW_FFMPEG = pathlib.Path.home() / ".cache/ms-playwright/ffmpeg-1011/ffmpeg-linux"
LIBRARY = pathlib.Path.home() / "Desktop/github_repos/videos-transcriptions"


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def ensure_ytdlp():
    if YTDLP.exists():
        return
    log(f"creating {VENV} with {YTDLP_PIN} (one time)")
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    subprocess.run([str(VENV / "bin/pip"), "install", "-q", YTDLP_PIN], check=True)


def ytdlp(*args, timeout=600):
    r = subprocess.run([str(YTDLP), "--js-runtimes", "node", "--no-warnings", *args],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        sys.exit(f"yt-dlp failed: {r.stderr.strip()[-800:]}")
    return r.stdout


def resolve(query):
    target = query if re.match(r"https?://", query) else f"ytsearch1:{query}"
    info = json.loads(ytdlp("-J", "--skip-download", target, timeout=180))
    if info.get("_type") == "playlist":
        if not info.get("entries"):
            sys.exit(f"no video found for {query!r}")
        info = info["entries"][0]
    return info


def pick_captions(info, lang):
    """Return (kind, key) - manual subtitles first, then auto-captions, in the original or requested language."""
    subs = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
    auto = info.get("automatic_captions") or {}
    orig = next((k[:-5] for k in auto if k.endswith("-orig")), None)
    want = lang or info.get("language")
    base = lambda k: k.split("-")[0].lower()
    if want:
        for k in subs:
            if k == want or base(k) == base(want):
                return "manual", k
        for k in (f"{want}-orig", want):
            if k in auto:
                return "auto", k
        if orig and base(orig) == base(want):
            return "auto", f"{orig}-orig"
    if not lang and subs:              # uploader's own subtitles beat a guessed auto-caption language
        return "manual", next(iter(subs))
    if not lang and orig:
        return "auto", f"{orig}-orig"
    return None, None


def ts(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def parse_vtt(text):
    """[(start_seconds, line)] with YouTube's rolling-caption repetition removed."""
    out, last = [], None
    for block in re.split(r"\n\s*\n", text):
        m = re.search(r"(\d+):(\d\d):(\d\d)\.(\d+)\s+-->", block) or re.search(r"(\d\d):(\d\d)\.(\d+)\s+-->", block)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] if len(g) == 4 else g[0] * 60 + g[1]
        for line in block.split("-->", 1)[1].split("\n")[1:]:
            line = html.unescape(re.sub(r"<[^>]+>", "", line)).replace("​", "").strip()
            if line and line != last:
                out.append((start, line))
                last = line
    return out


def paragraphs(segments, min_s=30, max_s=60):
    paras, cur, t0 = [], [], None
    for start, text in segments:
        if t0 is None:
            t0 = start
        cur.append(text)
        span = start - t0
        if (span >= min_s and re.search(r"[.!?…]['\")\]]?$", text)) or span >= max_s:
            paras.append((t0, " ".join(cur)))
            cur, t0 = [], None
    if cur:
        paras.append((t0, " ".join(cur)))
    return paras


def ffmpeg_bin():
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    if PW_FFMPEG.exists():
        log("system ffmpeg missing - trying Playwright's minimal ffmpeg (may not decode YouTube audio)")
        return str(PW_FFMPEG)
    return None


def multipart(fields, file_path):
    b = uuid.uuid4().hex
    body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
    body += (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
             f"Content-Type: application/octet-stream\r\n\r\n").encode() + file_path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    return body, f"multipart/form-data; boundary={b}"


def whisper(info, lang, work, chunk_min):
    try:
        ids = [m["id"] for m in json.loads(urllib.request.urlopen(SPEACHES + "/models", timeout=10).read())["data"]]
    except Exception as e:
        sys.exit(f"Speaches ({SPEACHES}) not reachable: {e} - start it: docker start speaches")
    if WHISPER not in ids:
        sys.exit(f"{WHISPER} not in Speaches models {ids}")
    log("downloading audio ...")
    ytdlp("-f", "bestaudio", "-o", str(work / "audio.%(ext)s"), info["webpage_url"], timeout=1800)
    audio = next(work.glob("audio.*"))
    ff = ffmpeg_bin()
    if ff:
        r = subprocess.run([ff, "-loglevel", "error", "-i", str(audio), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame",
                            "-b:a", "64k", "-f", "segment", "-segment_time", str(chunk_min * 60), str(work / "chunk%03d.mp3")])
        chunks = sorted(work.glob("chunk*.mp3")) if r.returncode == 0 else []
    else:
        chunks = []
    if not chunks:
        log("no usable ffmpeg - sending the whole audio file in one request (no progress until it ends)")
        chunks, chunk_min = [audio], 0
    segs, t_start = [], time.time()
    for i, c in enumerate(chunks):
        fields = {"model": WHISPER, "response_format": "verbose_json"}
        if lang:
            fields["language"] = lang.split("-")[0]
        body, ctype = multipart(fields, c)
        req = urllib.request.Request(SPEACHES + "/audio/transcriptions", data=body, headers={"Content-Type": ctype})
        d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
        lang = lang or d.get("language")
        off = i * chunk_min * 60
        segs += [(off + s["start"], s["text"].strip()) for s in d.get("segments", []) if s.get("text", "").strip()]
        done = time.time() - t_start
        log(f"chunk {i + 1}/{len(chunks)} done, {done:.0f} s elapsed, ETA {done / (i + 1) * (len(chunks) - i - 1):.0f} s")
    return segs, lang


def slug(s):
    raw = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    if len(raw) <= 60:
        return raw or "video"
    cut = raw[:60]
    return (cut.rsplit("-", 1)[0] if "-" in cut else cut) or "video"


def library_video_dir(info, date):
    """channels/<slug>/<date>--<id>--<title-slug>/ — reuse the folder whose CHANNEL.md has this channel id."""
    if not (LIBRARY / ".git").is_dir():
        sys.exit(f"video library missing. Clone it, then retry:\n"
                 f"gh repo clone michalkonik/videos-transcriptions {LIBRARY}")
    cid = info.get("channel_id") or ""
    cname = info.get("channel") or info.get("uploader") or "channel"
    dest = None
    root = LIBRARY / "channels"
    if root.is_dir() and cid:
        for ch in root.glob("*/CHANNEL.md"):
            if f"Channel ID: {cid}" in ch.read_text(errors="ignore"):
                dest = ch.parent
                break
    if dest is None:
        dest = root / slug(cname)
        marker = dest / "CHANNEL.md"
        if marker.exists() and cid and f"Channel ID: {cid}" not in marker.read_text(errors="ignore"):
            sys.exit(f"channel folder {dest} belongs to a different channel id")
        dest.mkdir(parents=True, exist_ok=True)
        if not marker.exists():
            marker.write_text(f"# {cname}\n\n- YouTube: {info.get('channel_url')}\n"
                              f"- Channel ID: {cid}\n- Slug: {dest.name}\n")
    video = dest / f"{date}--{info.get('id')}--{slug(info.get('title') or 'video')}"
    video.mkdir(parents=True, exist_ok=True)
    return video


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--lang")
    ap.add_argument("--whisper", action="store_true")
    ap.add_argument("--pick-only", action="store_true")
    ap.add_argument("--out", default=str(pathlib.Path.home() / "Documents/transcripts"))
    ap.add_argument("--basename", help="file name inside --out; default <upload-date>-<slug>.md")
    ap.add_argument("--library", action="store_true",
                    help="write transcript.md into ~/Desktop/github_repos/videos-transcriptions, grouped by channel")
    ap.add_argument("--chunk-min", type=int, default=10)
    a = ap.parse_args()
    ensure_ytdlp()
    t0 = time.time()
    info = resolve(a.query)
    dur = info.get("duration") or 0
    print(f"video: {info.get('title')} | {info.get('channel') or info.get('uploader')} | {info.get('upload_date')} | "
          f"{ts(dur)} | {info.get('webpage_url')}")
    manual = [k for k in (info.get("subtitles") or {}) if k != "live_chat"]
    orig = next((k[:-5] for k in (info.get("automatic_captions") or {}) if k.endswith("-orig")), None)
    print(f"captions: manual {', '.join(manual[:12]) or 'none'}; auto-captions original language: {orig or 'none'}")
    if a.pick_only:
        return
    kind, key = (None, None) if a.whisper else pick_captions(info, a.lang)
    with tempfile.TemporaryDirectory(prefix="yt-transcript-") as tmp:
        work = pathlib.Path(tmp)
        segs = []
        if kind:
            flag = "--write-subs" if kind == "manual" else "--write-auto-subs"
            ytdlp("--skip-download", flag, "--sub-langs", key, "--sub-format", "vtt", "-o", str(work / "subs"),
                  info["webpage_url"], timeout=300)
            vtt = next(work.glob("subs*.vtt"), None)
            segs = parse_vtt(vtt.read_text(errors="ignore")) if vtt else []
            lang, source = key.replace("-orig", ""), f"captions ({kind})"
        if not segs:
            if kind:
                log("captions empty - falling back to Whisper")
            log(f"transcribing {ts(dur)} of audio on CPU with {WHISPER} (roughly 1/5-1/10 of the duration)")
            segs, lang = whisper(info, a.lang, work, a.chunk_min)
            source = f"whisper ({WHISPER} via Speaches)"
    paras = paragraphs(segs)
    d = info.get("upload_date") or datetime.date.today().strftime("%Y%m%d")
    date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if a.library:
        path = library_video_dir(info, date) / "transcript.md"
    else:
        out = pathlib.Path(a.out).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        name = a.basename or f"{date}-{slug(info.get('title', 'video'))}.md"
        if name != pathlib.Path(name).name or not name.endswith(".md"):
            sys.exit("basename must be a single .md file name")
        path = out / name
    head = (f"# {info.get('title')}\n\n"
            f"- Channel: {info.get('channel') or info.get('uploader')}\n"
            f"- Channel URL: {info.get('channel_url')}\n- Channel ID: {info.get('channel_id')}\n"
            f"- Video ID: {info.get('id')}\n- Published: {date}\n- Duration: {ts(dur)}\n"
            f"- URL: {info.get('webpage_url')}\n- Language: {lang}\n- Source: {source}\n"
            f"- Transcribed: {datetime.datetime.now():%Y-%m-%d %H:%M}\n\n## Transcript\n\n")
    text = head + "\n\n".join(f"[{ts(t)}] {p}" for t, p in paras) + "\n"
    desc = (info.get("description") or "").strip()
    if desc:
        text += f"\n## Description\n\n{desc}\n"
    path.write_text(text)
    words = sum(len(p.split()) for _, p in paras)
    print(f"saved {path}\nsource {source}, language {lang}, {words} words, {len(paras)} paragraphs, {time.time() - t0:.0f} s")
    if a.library:
        print(f"summary {path.parent / 'summary.md'}\nshape {LIBRARY / 'README.md'}")


if __name__ == "__main__":
    main()
