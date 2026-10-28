#!/usr/bin/env python3
"""Turn a scene script (script.json) into a finished video: narration (Kokoro via Speaches), frames (headless
Chrome), captions, chapters, mp4 (ffmpeg). Everything local. Re-runs only redo what changed.

  video.py schema                          the script.json format (read this before writing a script)
  video.py new SLUG [--short]              create ~/content/videos/SLUG/ with an empty script.json
  video.py capture SLUG NAME -- CMD...     run a real command now, save its output for a terminal scene
  video.py check SLUG                      validate script.json; estimated length; problems to fix (exit 1 = errors)
  video.py all SLUG                        check + tts + render + build + report (the normal way)
  video.py tts|render|build|report SLUG    single stages
  video.py frame SLUG SCENE [BEAT]         render one frame to out/preview.png (look at a scene before the full run)

Outputs in ~/content/videos/SLUG/out/: video.mp4, captions.srt, chapters.txt, report.txt.
"""
import concurrent.futures, hashlib, json, math, os, pathlib, re, shutil, subprocess, sys, time, urllib.request, wave

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "lib"))
import content  # noqa: E402

FPS_TYPE = 15            # frames per second while a command is being typed
PAUSE, SCENE_PAUSE = 0.30, 0.55
LONG, SHORT = (1920, 1080), (1080, 1920)
STAGE = hashlib.sha1((HERE / "stage.html").read_bytes()).hexdigest()[:8]   # template change -> frames re-render
TYPES = {"title", "bullets", "big", "terminal", "code", "chart", "flow", "table", "image"}

SCHEMA = """script.json = {"title": str, "short": bool, "voice": optional Kokoro voice, "scenes": [SCENE...]}
Every SCENE has "type" and "say": [str, ...]  - one string per beat. A beat = one narration line + one visual step.
Write "say" as SPOKEN words (numbers as you would say them is fine; avoid symbols). 1-3 sentences per beat.
Optional on any scene: "chapter": "Name" (starts a YouTube chapter), "source": "where a number comes from".
Types (visual for beat i in brackets):
  title    {heading, sub}                                   [static]   heading: *word* = accent colour
  bullets  {heading, items:[str]}                           [reveals items one per beat; len(say)=len(items)+1 -> beat 0 = heading only]
  big      {value:"142 tok/s", text}                        [static]   one number that matters
  terminal {heading?, capture:"NAME"} or {cmd, output}      [beat 0 types the command, later beats reveal output]
           capture = output saved by `video.py capture` (REAL, preferred). Hand-written output needs "illustrative": true
           optional "cmd": short command to SHOW (e.g. "python3 bench_conc.py gemma-pool") instead of the long real one;
           capture commands whose output reads well (a summary, `| tail -15`), not raw dumps
  code     {heading?, lang:"yaml|python|bash|json|toml", code, highlight:[[from,to] per beat]}  (line numbers start at 1)
  chart    {heading, unit, bars:[[label, value, "shown text"?]], lower_is_better?}   [reveals bars; best bar in accent]
  flow     {heading, nodes:[str or [str, "small note"]]}    [reveals nodes left->right with arrows]
  table    {heading, columns:[..], rows:[[..]], win:[[row,col]]}  [reveals rows]
  image    {heading?, src:"assets/x.png", caption?}         [static; screenshots, photos of the rig, ComfyUI art]
Rules: first scene = the hook (title or big, max 2 beats, <= 30 words). Long video: 8-15 min = 1200-2200 spoken words,
a visual change at least every ~20 s, chapters on the first scene and every major section (>= 3, each >= 10 s).
Short: "short": true, 30-55 s, 80-125 words, hook in the first beat, one idea, no chapters."""


def die(msg):
    print("ERROR", msg)
    sys.exit(1)


def proj(slug):
    d = content.VIDEOS / slug
    if not (d / "script.json").is_file():
        die(f"{d}/script.json not found (video.py new {slug})")
    return d


def load(d):
    try:
        sc = json.loads((d / "script.json").read_text())
    except json.JSONDecodeError as e:
        die(f"script.json is not valid JSON: {e}")
    for s in sc.get("scenes", []):
        if s.get("capture"):
            f = d / "captures" / f"{s['capture']}.json"
            if f.is_file():
                c = json.loads(f.read_text())
                s.setdefault("cmd", c["cmd"])
                s.setdefault("output", c["output"])
    return sc


def beats(sc):
    for i, s in enumerate(sc["scenes"]):
        for j, t in enumerate(s.get("say") or []):
            yield i, j, t


def spoken(text, ch):
    """Text for the TTS engine: expand symbols and jargon Kokoro mispronounces. Channel 'pronounce' overrides."""
    rules = [(r"\btok/s\b|\bt/s\b|tokens/s\b", "tokens per second"), (r"llama\.cpp", "llama C P P"),
             (r"\bvLLM\b", "V L L M"), (r"\bLLMs\b", "L L Ms"), (r"\bLLM\b", "L L M"), (r"\bGGUF\b", "G G U F"),
             (r"\bVRAM\b", "V RAM"), (r"\bROCm\b", "rock M"), (r"\bMoE\b", "M O E"), (r"\bQwen", "Kwen"),
             (r"\bKV\b", "K V"), (r"\bMTP\b", "M T P"), (r"\bUI\b", "U I"), (r"\bAPI\b", "A P I"),
             (r"\bR9700\b", "R ninety-seven hundred"), (r"(\d)\s?GB\b", r"\1 gigabytes"), (r"(\d)\s?TB\b", r"\1 terabytes"),
             (r"(\d)\s?ms\b", r"\1 milliseconds"), (r"(\d)%", r"\1 percent"), (r"\b(\d+)B\b", r"\1 B"),
             (r"_", " "), (r"\bvs\.?\b", "versus"), (r"\be\.g\.", "for example"), (r"\bi\.e\.", "that is")]
    for k, v in (ch.get("pronounce") or {}).items():
        rules.insert(0, (re.escape(k), v))
    for pat, rep in rules:
        text = re.sub(pat, rep, text)
    return text


# ---------------------------------------------------------------- check
def check(d, quiet=False):
    sc = load(d)
    short = bool(sc.get("short"))
    err, warn = [], []
    scenes = sc.get("scenes") or []
    if not scenes:
        err.append("no scenes")
    words = 0
    for i, s in enumerate(scenes):
        tag = f"scene {i} ({s.get('type')})"
        if s.get("type") not in TYPES:
            err.append(f"{tag}: unknown type; use one of {sorted(TYPES)}")
            continue
        say = s.get("say") or []
        if not say or not all(isinstance(t, str) and t.strip() for t in say):
            err.append(f"{tag}: 'say' must be a non-empty list of strings")
            continue
        w = sum(len(t.split()) for t in say)
        words += w
        for j, t in enumerate(say):
            if len(t.split()) > 70:
                warn.append(f"{tag} beat {j}: {len(t.split())} words (> 70 - split it, the picture goes stale)")
        need = {"bullets": "items", "chart": "bars", "flow": "nodes", "table": "rows", "code": "code", "big": "value",
                "title": "heading", "image": "src"}.get(s["type"])
        if need and not s.get(need):
            err.append(f"{tag}: missing '{need}'")
        if s["type"] == "terminal":
            if s.get("capture") and not (d / "captures" / f"{s['capture']}.json").is_file():
                err.append(f"{tag}: capture '{s['capture']}' not found - run: video.py capture {d.name} {s['capture']} -- CMD")
            elif not s.get("capture") and not s.get("illustrative"):
                err.append(f"{tag}: no capture - record the real output (video.py capture) or mark \"illustrative\": true")
        if s["type"] == "image" and s.get("src") and not (d / s["src"]).is_file():
            err.append(f"{tag}: image {s['src']} not found in {d}")
        if s["type"] == "code" and s.get("highlight") and len(s["highlight"]) > len(say):
            warn.append(f"{tag}: more highlight ranges than beats")
        if s["type"] in ("chart", "big") and not s.get("source"):
            warn.append(f"{tag}: add 'source' (where the number comes from) - viewers check")
    # Kokoro at speed 1.0 says ~2.4 words/s; plus the pauses video.py inserts (measured: 129 words -> 58 s)
    secs = words / 2.4 + sum(len(s.get("say") or []) for s in scenes) * PAUSE + len(scenes) * (SCENE_PAUSE - PAUSE)
    if scenes:
        hook = scenes[0]
        if hook.get("type") not in ("title", "big") or len(hook.get("say") or []) > 2 or \
                sum(len(t.split()) for t in hook.get("say") or []) > 30:
            warn.append("scene 0 should be the hook: type title/big, <= 2 beats, <= 30 words")
    chapters = [s for s in scenes if s.get("chapter")]
    if short:
        if not 20 <= secs <= 56:
            warn.append(f"short is ~{secs:.0f} s (aim 30-55 s; over 60 s it is not a Short) - trim to ~125 words")
        if chapters:
            warn.append("shorts have no chapters - remove 'chapter'")
    else:
        if chapters and (not scenes[0].get("chapter") or len(chapters) < 3):
            warn.append("chapters: the first scene needs one and there must be >= 3 (YouTube rule)")
        if secs < 240:
            warn.append(f"long video is only ~{secs/60:.1f} min")
    narration = "\n".join(t for _, _, t in beats(sc))
    score, tells = content.lint(narration)
    if score > 3:
        warn.append("narration sounds generated: " + "; ".join(tells[:8]))
    if not quiet or err or warn:
        print(f"{d.name}: {len(scenes)} scenes, {sum(1 for _ in beats(sc))} beats, {words} words, ~{secs/60:.1f} min"
              f" {'(short)' if short else ''}")
        for e in err:
            print("ERROR", e)
        for w in warn:
            print("WARN ", w)
    return not err


# ---------------------------------------------------------------- tts
def tts(d):
    sc, ch = load(d), content.channel()
    voice = sc.get("voice") or ch["tts_voice"]
    (d / "audio").mkdir(exist_ok=True)
    jobs = []
    for i, j, t in beats(sc):
        say = spoken(t, ch)
        key = hashlib.sha1(f"{ch['tts_model']}|{voice}|{ch['tts_speed']}|{say}".encode()).hexdigest()[:16]
        jobs.append((d / "audio" / f"{key}.wav", say))
    todo = [(p, s) for p, s in jobs if not p.is_file()]

    def one(job):
        p, s = job
        body = {"model": ch["tts_model"], "voice": voice, "input": s, "response_format": "wav", "speed": ch["tts_speed"]}
        req = urllib.request.Request(content.SPEACHES + "/audio/speech", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    p.write_bytes(r.read())
                return
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    raise SystemExit(f"ERROR Speaches TTS failed ({e}); is it running? docker start speaches")
                time.sleep(3)

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        list(ex.map(one, todo))
    (d / "audio" / "beats.json").write_text(json.dumps([str(p.name) for p, _ in jobs]))
    total = sum(wav_len(p) for p, _ in jobs)
    print(f"tts: {len(todo)} new / {len(jobs)} beats, narration {total/60:.1f} min, {time.time()-t0:.0f} s")


def wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- render
def timeline(d, sc):
    """[(scene, beat, start, dur, wav)] with pauses included in dur."""
    names = json.loads((d / "audio" / "beats.json").read_text())
    out, t, k = [], 0.0, 0
    for i, s in enumerate(sc["scenes"]):
        n = len(s["say"])
        for j in range(n):
            wav = d / "audio" / names[k]
            dur = wav_len(wav) + (SCENE_PAUSE if j == n - 1 else PAUSE)
            out.append((i, j, t, dur, wav))
            t += dur
            k += 1
    return out


def ensure_node():
    if not (HERE / "node_modules" / "playwright-core").is_dir():
        print("installing playwright-core for the renderer (once)...")
        r = subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=HERE)
        if r.returncode:
            die("npm install failed in " + str(HERE))


def render(d, only=None):
    sc, ch = load(d), content.channel()
    short = bool(sc.get("short"))
    w, h = SHORT if short else LONG
    fr = d / "frames"
    fr.mkdir(exist_ok=True)
    items, frames = [], []
    tl = timeline(d, sc) if only is None else [(only[0], only[1], 0, 1, None)]
    for i, j, start, dur, _ in tl:
        s = sc["scenes"][i]
        key = hashlib.sha1(json.dumps([STAGE, s, j, short, ch["accent"], ch.get("youtube_handle")], sort_keys=True).encode()).hexdigest()[:12]
        if s["type"] == "terminal" and j == 0 and s.get("cmd"):
            typing = min(2.2, 0.45 * dur)
            nf = max(2, round(typing * FPS_TYPE))
            for f in range(nf):
                typed = round(len(s["cmd"]) * (f + 1) / nf)
                out = fr / f"{key}_t{f:03d}.png"
                items.append({"s": i, "beat": j, "opts": {"typed": typed}, "out": str(out)})
                frames.append((out, 1 / FPS_TYPE if f < nf - 1 else dur - typing + 1 / FPS_TYPE))
        else:
            out = fr / f"{key}.png"
            items.append({"s": i, "beat": j, "opts": {}, "out": str(out)})
            frames.append((out, dur))
    if only is not None:
        items[-1]["out"] = str(d / "out" / "preview.png")
        (d / "out").mkdir(exist_ok=True)
    handle = ch.get("youtube_handle") if ch.get("youtube_handle", "@") != "@" else ""
    plan = {"width": w, "height": h, "short": short, "brand": handle, "dir": str(d), "force": only is not None,
            "vars": {"--accent": ch["accent"], "--bg": ch["bg"], "--fg": ch["fg"]}, "scenes": sc["scenes"],
            "items": items}
    (d / "plan.json").write_text(json.dumps(plan))
    ensure_node()
    r = subprocess.run(["node", str(HERE / "render.mjs"), str(d / "plan.json")], capture_output=True, text=True)
    if r.returncode:
        die("render failed: " + (r.stderr or r.stdout)[-1500:])
    print("render:", r.stdout.strip())
    if only is None:
        (d / "frames.json").write_text(json.dumps([[str(p), du] for p, du in frames]))


# ---------------------------------------------------------------- build
def ts(t, sep=","):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", sep)


def chunks(text, short):
    """Split one beat's text into caption chunks: ~4 words for shorts, <= 2 lines of 42 chars for long."""
    words = text.split()
    if short:
        return [" ".join(words[i:i + 4]) for i in range(0, len(words), 4)]
    out, cur = [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > 84 or (len(cur) > 40 and cur.endswith((".", "?", "!", ","))):
            out.append(cur.strip())
            cur = ""
        cur += " " + wd
    return out + ([cur.strip()] if cur.strip() else [])


def captions(sc, tl, short):
    cues = []
    for i, j, start, dur, wav in tl:
        speech = wav_len(wav)
        parts = chunks(sc["scenes"][i]["say"][j], short)
        total = sum(len(p) for p in parts) or 1
        t = start
        for p in parts:
            dt = speech * len(p) / total
            cues.append((t, t + dt, p))
            t += dt
    return cues


def build(d):
    sc = load(d)
    short = bool(sc.get("short"))
    tl = timeline(d, sc)
    out = d / "out"
    out.mkdir(exist_ok=True)
    # narration: every beat's wav followed by its pause, one file
    with wave.open(str(tl[0][4])) as w0:
        params = w0.getparams()
    narr = d / "narration.wav"
    with wave.open(str(narr), "wb") as o:
        o.setparams(params)
        for _, _, _, dur, wav in tl:
            with wave.open(str(wav)) as w:
                data = w.readframes(w.getnframes())
            o.writeframes(data)
            pad = int(round((dur - wav_len(wav)) * params.framerate))
            o.writeframes(b"\x00" * pad * params.sampwidth * params.nchannels)
    frames = json.loads((d / "frames.json").read_text())
    lst = d / "frames.txt"
    lines = []
    for p, du in frames:
        lines += [f"file '{p}'", f"duration {du:.4f}"]
    lines.append(f"file '{frames[-1][0]}'")
    lst.write_text("\n".join(lines) + "\n")
    cues = captions(sc, tl, short)
    srt = out / "captions.srt"
    srt.write_text("\n".join(f"{k}\n{ts(a)} --> {ts(b)}\n{t}\n" for k, (a, b, t) in enumerate(cues, 1)))
    chap = [(start, sc["scenes"][i]["chapter"]) for i, j, start, _, _ in tl if j == 0 and sc["scenes"][i].get("chapter")]
    (out / "chapters.txt").write_text("".join(f"{int(a//60)}:{int(a%60):02d} {n}\n" for a, n in chap))
    meta = d / "ffmeta.txt"
    total = tl[-1][2] + tl[-1][3]
    m = [";FFMETADATA1", f"title={sc.get('title', d.name)}"]
    for k, (a, n) in enumerate(chap):
        b = chap[k + 1][0] if k + 1 < len(chap) else total
        m += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(a*1000)}", f"END={int(b*1000)}", f"title={n}"]
    meta.write_text("\n".join(m) + "\n")
    vf = "fps=30,format=yuv420p"
    if short:
        ass = d / "captions.ass"
        ass.write_text(ass_file(cues))
        vf = f"fps=30,subtitles={ass}:fontsdir=/usr/share/fonts,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(narr),
           "-i", str(meta), "-map_metadata", "2", "-map_chapters", "2", "-vf", vf, "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
           "-shortest", "-movflags", "+faststart", str(out / "video.mp4")]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        die("ffmpeg: " + r.stderr[-1500:])
    print(f"build: out/video.mp4 {total/60:.1f} min in {time.time()-t0:.0f} s; captions.srt ({len(cues)} cues); "
          f"{len(chap)} chapters")


def ass_file(cues):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: C,DejaVu Sans,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,430,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    t = lambda x: f"{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}"
    return head + "".join(f"Dialogue: 0,{t(a)},{t(b)},C,,0,0,0,,{txt.upper()}\n" for a, b, txt in cues)


# ---------------------------------------------------------------- report
def report(d):
    v = d / "out" / "video.mp4"
    if not v.is_file():
        die("no out/video.mp4 yet")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height",
                        "-of", "json", str(v)], capture_output=True, text=True)
    info = json.loads(r.stdout)
    dur = float(info["format"]["duration"])
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    sc = load(d)
    lines = [f"video: {v} ({vs['width']}x{vs['height']}, {int(dur//60)}:{int(dur%60):02d}, "
             f"{int(info['format']['size'])/1e6:.0f} MB)",
             f"captions: {d/'out'/'captions.srt'}", f"chapters: {(d/'out'/'chapters.txt').read_text().strip() or '-'}"]
    if sc.get("short") and dur > 60:
        lines.append("WARN short is longer than 60 s")
    thumb = d / "out" / "thumbnail.png"
    lines.append(f"thumbnail: {thumb if thumb.is_file() else 'MISSING - run thumb.py'}")
    (d / "out" / "report.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def capture(slug, name, cmd):
    d = content.VIDEOS / slug
    (d / "captures").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1800)
    out = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout + r.stderr).replace("\r", "")
    lines = out.rstrip().split("\n")
    (d / "captures" / f"{name}.log").write_text(out)
    if len(lines) > 30:
        lines = lines[:6] + [f"... ({len(lines) - 26} lines) ..."] + lines[-20:]
    rec = {"cmd": cmd, "output": "\n".join(l[:150] for l in lines), "rc": r.returncode,
           "seconds": round(time.time() - t0, 1), "at": time.strftime("%Y-%m-%d %H:%M")}
    (d / "captures" / f"{name}.json").write_text(json.dumps(rec, indent=1))
    print(f"captured {name}: rc {r.returncode}, {rec['seconds']} s, {len(out.splitlines())} lines "
          f"(shown: {len(lines)}); last line: {lines[-1][:120] if lines else ''}")


def new(slug, short):
    d = content.VIDEOS / slug
    if (d / "script.json").exists():
        die(f"{d} already exists")
    for sub in ("captures", "assets", "out"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    (d / "script.json").write_text(json.dumps({"title": "", "short": short, "scenes": []}, indent=1) + "\n")
    print(f"created {d}/script.json - read `video.py schema`, then fill it")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    cmd = a[0]
    if cmd == "schema":
        print(SCHEMA)
    elif cmd == "new":
        new(a[1], "--short" in a)
    elif cmd == "capture":
        if "--" not in a:
            die("usage: video.py capture SLUG NAME -- CMD")
        k = a.index("--")
        capture(a[1], a[2], " ".join(a[k + 1:]))
    else:
        d = proj(a[1])
        if cmd == "check":
            sys.exit(0 if check(d) else 1)
        elif cmd == "tts":
            tts(d)
        elif cmd == "render":
            render(d)
        elif cmd == "frame":
            render(d, only=(int(a[2]), int(a[3]) if len(a) > 3 else 0))
            print(f"preview: {d/'out'/'preview.png'}")
        elif cmd == "build":
            build(d)
        elif cmd == "report":
            report(d)
        elif cmd == "all":
            if not check(d):
                sys.exit(1)
            tts(d)
            render(d)
            build(d)
            report(d)
        else:
            die(f"unknown command {cmd}")
