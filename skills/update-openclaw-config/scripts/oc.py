#!/usr/bin/env python3
"""Helper for /update-openclaw-config: see the current OpenClaw setup, find config paths and docs, back up, diff, log.

  oc.py state                      one-page summary: gateway, agents, models (vs llama-swap), plugins, skills,
                                   MCP, channels, tools, recent patches/backups (secrets redacted)
  oc.py schema PATH                one config path from the JSON schema: type, title, description, enum, bounds,
                                   children (e.g. agents.entries.miclaw.subagents, models.providers.vllm.models[])
  oc.py find REGEX [N]             config paths whose name/title/description match (default 40 hits)
  oc.py docs REGEX [N]             the offline docs pages that match best, with their summary (default 12)
  oc.py backup WHAT [FILE ...]     copy openclaw.json to ~/.openclaw/openclaw.json.bak-<date>-<what> (+ other files,
                                   e.g. workspace .md, to ~/.local/state/rig-skills/backups/) and print the undo
  oc.py diff [OLD] [NEW]           what changed, path by path, secrets redacted (default: newest .bak-* vs current)
  oc.py test AGENT "MESSAGE" [--model provider/model] [--timeout S]
                                   one real turn in a NEW session (agent:<id>:oc-test-<time>) and a summary: reply,
                                   effective model, fallback, workspace files, skills and tools the agent got
  oc.py log "<what; why; undo>"    one line in ~/.local/state/rig-skills/journal.log

Read-only except backup, log and test (test creates one throwaway session). The change itself is made with `openclaw config patch` (see SKILL.md).
"""
import datetime, json, pathlib, re, shutil, subprocess, sys, textwrap
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import rig

OC_DIR = rig.HOME / ".openclaw"
CONFIG = OC_DIR / "openclaw.json"
PATCHES = OC_DIR / "patches"
DOCS = rig.HOME / ".npm-global/lib/node_modules/openclaw/docs"
CACHE = rig.STATE / "openclaw"
SECRET = re.compile(r"(token|secret|password|passwd|api_?key|private_?key|client_?key|cookie|credential)", re.I)


def oc_bin():
    return shutil.which("openclaw") or str(rig.HOME / ".npm-global/bin/openclaw")


def oc(*args, timeout=60):
    """Run the OpenClaw CLI with a hard timeout (some subcommands, e.g. doctor, can hang)."""
    try:
        r = subprocess.run(["timeout", str(timeout), oc_bin(), *args], capture_output=True, text=True,
                           timeout=timeout + 5)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def load(path=CONFIG):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except ValueError:
        sys.exit(f"{path} is not plain JSON (comments/JSON5?) - use `openclaw config get <path> --json` instead")


def redact(o, key="", parent=""):
    if isinstance(o, dict):
        return {k: redact(v, k, key) for k, v in o.items()}
    if isinstance(o, list):
        return [redact(v, key, parent) for v in o]
    if isinstance(o, str) and o and (SECRET.search(key) or parent in ("env", "headers")):
        return "<redacted>"
    return o


def flatten(o, prefix=""):
    if isinstance(o, dict) and o:
        out = {}
        for k, v in o.items():
            if re.fullmatch(r"[A-Za-z0-9_-]+", k):
                out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
            else:
                out.update(flatten(v, f"{prefix}[{json.dumps(k)}]"))
        return out
    return {prefix: o}


# ---------------------------------------------------------------- state
def state():
    rc, out, _ = oc("--version")
    st = CONFIG.stat()
    print(f"{out.strip()}  config {CONFIG} ({st.st_size} B, modified {datetime.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M})")
    svc = subprocess.run(["systemctl", "--user", "is-active", "openclaw-gateway"], capture_output=True, text=True).stdout.strip()
    c = redact(load())
    gw = c.get("gateway", {})
    print(f"gateway: service openclaw-gateway {svc}; {gw.get('bind', '?')}:{gw.get('port', 18789)}, auth {gw.get('auth', {}).get('mode')}, "
          f"reload {gw.get('reload', {}).get('mode', 'hybrid (default)')}")
    rc, out, err = oc("health", timeout=30)
    for line in (out + err).splitlines():
        if re.search(r"fail|error|warn", line, re.I):
            print(f"  health: {line.strip()[:160]}")
    ag = c.get("agents", {})
    d = ag.get("defaults", {})
    print(f"agents.defaults: model {json.dumps(d.get('model'))}; models {list(d.get('models', {}))}; "
          f"modelPolicy {json.dumps(d.get('modelPolicy'))}; skills {json.dumps(d.get('skills', 'all'))}")
    print(f"  subagents {json.dumps(d.get('subagents'))}; workspace {d.get('workspace')}; timeoutSeconds {d.get('timeoutSeconds', 'default')}")
    for aid, a in ag.get("entries", {}).items():
        extra = {k: v for k, v in a.items() if k not in ("name", "workspace", "agentDir", "identity")}
        idn = a.get("identity", {})
        print(f"agent {aid}: \"{idn.get('name', a.get('name'))}\" workspace {a.get('workspace')}; {json.dumps(extra)}")
        ws = pathlib.Path(a.get("workspace") or d.get("workspace") or OC_DIR / "workspace")
        if ws.is_dir():
            files = sorted(p.name for p in ws.glob("*.md"))
            skills = sorted(p.parent.name for p in ws.glob("skills/**/SKILL.md"))
            print(f"  workspace files: {', '.join(files)}; workspace skills: {', '.join(skills) or 'none'}")
    try:
        ls_ids = {m["id"] for m in rig.http_json(rig.LS_URL + "/v1/models")["data"]}
    except Exception as e:
        ls_ids = None
        print(f"llama-swap not reachable: {e}")
    for pid, p in c.get("models", {}).get("providers", {}).items():
        print(f"provider {pid}: {p.get('baseUrl')} api {p.get('api')}")
        for m in p.get("models", []):
            miss = "" if ls_ids is None or pid != "vllm" or m["id"] in ls_ids else "   <-- NOT a llama-swap model id"
            print(f"  {pid}/{m['id']}  ctx {m.get('contextWindow')} maxTokens {m.get('maxTokens')} input {m.get('input')}{miss}")
    if ls_ids is not None:
        print(f"llama-swap models: {', '.join(sorted(ls_ids))}; running now: {', '.join(rig.running()) or 'none'}")
    pe = c.get("plugins", {}).get("entries", {})
    on = [k for k, v in pe.items() if v.get("enabled")]
    off = [k for k, v in pe.items() if v.get("enabled") is False]
    print(f"plugins.entries enabled: {', '.join(on)}; disabled: {', '.join(off) or 'none'}; "
          f"configured: {', '.join(k for k, v in pe.items() if 'config' in v) or 'none'}")
    se = c.get("skills", {}).get("entries", {})
    print(f"skills.entries: {sum(1 for v in se.values() if v.get('enabled') is False)} disabled, "
          f"{', '.join(k for k, v in se.items() if v.get('enabled') is not False) or 'none'} explicitly on; "
          f"extraDirs {c.get('skills', {}).get('load', {}).get('extraDirs', [])}")
    print(f"mcp.servers: {', '.join(c.get('mcp', {}).get('servers', {})) or 'none'}")
    print(f"channels: {', '.join(c.get('channels', {})) or 'none configured'}; bindings: {len(c.get('bindings', []))}")
    print(f"tools: {json.dumps(c.get('tools', {}))}; browser: {json.dumps(c.get('browser', 'defaults'))}")
    pats = sorted(PATCHES.glob("*.json5"))[-5:] if PATCHES.is_dir() else []
    baks = sorted(OC_DIR.glob("openclaw.json.bak-*"), key=lambda p: p.stat().st_mtime)[-3:]
    print(f"recent patches: {', '.join(p.name for p in pats) or 'none'}; backups: {', '.join(p.name for p in baks) or 'none'}")


# ---------------------------------------------------------------- schema
def schema():
    rc, out, _ = oc("--version")
    ver = (re.findall(r"\d{4}\.\d+\.\d+", out) or ["unknown"])[0]
    f = CACHE / f"schema-{ver}.json"
    if not f.is_file():
        rc, out, err = oc("config", "schema", timeout=90)
        if rc != 0:
            sys.exit(f"openclaw config schema failed: {err[-500:]}")
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(out)
    return json.loads(f.read_text())


def split_path(path):
    return [a or b or c for a, b, c in re.findall(r'\["([^"]+)"\]|\[(\d+|\*)?\]|([^.\[\]]+)', path)] if path else []


def deref(node, defs):
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 10:
        name = node["$ref"].rsplit("/", 1)[-1]
        node = {**defs.get(name, {}), **{k: v for k, v in node.items() if k != "$ref"}}
        seen += 1
    return node


def branches(node, defs):
    node = deref(node, defs)
    alts = node.get("anyOf") or node.get("oneOf") or []
    out = [node] + [deref(a, defs) for a in alts] + [deref(a, defs) for a in node.get("allOf", [])]
    return out


def step(node, seg, defs):
    for b in branches(node, defs):
        defs = {**defs, **b.get("$defs", {})}
        if seg in b.get("properties", {}):
            return b["properties"][seg], defs
    for b in branches(node, defs):
        if (seg in ("", "*") or seg.isdigit()) and isinstance(b.get("items"), dict):
            return b["items"], defs
        for pat, sub in b.get("patternProperties", {}).items():
            if re.search(pat, seg):
                return sub, defs
        if isinstance(b.get("additionalProperties"), dict) and b["additionalProperties"]:
            return b["additionalProperties"], defs
        if isinstance(b.get("items"), dict):
            return b["items"], defs
    return None, defs


def typ(node, defs):
    ts = []
    for b in branches(node, defs):
        t = b.get("type")
        if t:
            ts += t if isinstance(t, list) else [t]
        if "const" in b:
            ts.append(json.dumps(b["const"]))
        if "enum" in b:
            ts.append("|".join(json.dumps(e) for e in b["enum"]))
    return " or ".join(dict.fromkeys(ts)) or "any"


def show(path):
    root = schema()
    node, defs = root, root.get("$defs", {})
    for seg in split_path(path):
        nxt, defs = step(node, seg, defs)
        if nxt is None:
            keys = sorted({k for b in branches(node, defs) for k in b.get("properties", {})})
            sys.exit(f"no '{seg}' under this node. Keys here: {', '.join(keys) or '(none - free-form)'}\n"
                     f"Try: oc.py find {seg}")
        node = nxt
        defs = {**defs, **deref(node, defs).get("$defs", {})}
    bs = branches(node, defs)
    meta = next((b for b in bs if b.get("title") or b.get("description")), bs[0])
    print(f"{path or '(root)'}: {typ(node, defs)}")
    if meta.get("title"):
        print(f"  title: {meta['title']}")
    if meta.get("description"):
        print(textwrap.fill(meta["description"], 116, initial_indent="  ", subsequent_indent="  "))
    for b in bs:
        lim = {k: b[k] for k in ("default", "minimum", "maximum", "exclusiveMinimum", "minItems", "maxItems",
                                 "pattern", "required") if k in b}
        if lim:
            print(f"  {json.dumps(lim)[:300]}")
    for b in bs:
        props = b.get("properties", {})
        for k, v in sorted(props.items()):
            vv = deref(v, defs)
            print(f"  .{k}: {typ(v, defs)}  {(vv.get('title') or vv.get('description') or '')[:90]}")
        ap = b.get("additionalProperties")
        if isinstance(ap, dict) and ap:
            pn = b.get("propertyNames", {}).get("pattern", "")
            print(f"  .<key>{' ' + pn if pn else ''}: map of {typ(ap, defs)} -> oc.py schema '{path}.<key>'")
        if isinstance(b.get("items"), dict):
            print(f"  []: items are {typ(b['items'], defs)} -> oc.py schema '{path}[]'")


def walk(node, defs, path, depth, out, seen):
    if depth > 12 or len(out) > 60000:
        return
    for b in branches(node, defs):
        d2 = {**defs, **b.get("$defs", {})}
        for k, v in b.get("properties", {}).items():
            p = f"{path}.{k}" if path else k
            if p in seen:
                continue
            seen.add(p)
            vv = deref(v, d2)
            out.append((p, vv.get("title", ""), vv.get("description", "")))
            walk(v, d2, p, depth + 1, out, seen)
        ap = b.get("additionalProperties")
        if isinstance(ap, dict) and ap:
            walk(ap, d2, f"{path}.<key>", depth + 1, out, seen)
        if isinstance(b.get("items"), dict):
            walk(b["items"], d2, f"{path}[]", depth + 1, out, seen)


def find(rx, n=40):
    root = schema()
    out = []
    walk(root, root.get("$defs", {}), "", 0, out, set())
    r = re.compile(rx, re.I)
    hits = [(0 if r.search(p.rsplit(".", 1)[-1]) else 1 if r.search(p + " " + t) else 2, p, t, d)
            for p, t, d in out if r.search(f"{p} {t} {d}")]
    hits.sort(key=lambda h: (h[0], len(h[1])))
    for _, p, t, d in hits[:n]:
        print(f"{p}  -  {(t or d)[:100]}")
    print(f"({len(hits)} matches{', showing ' + str(n) if len(hits) > n else ''}; details: oc.py schema <path>)")


def docs(rx, n=12):
    r = re.compile(rx, re.I)
    res = []
    for f in DOCS.rglob("*.md"):
        txt = f.read_text(errors="ignore")
        head = txt[:1500]
        score = len(r.findall(txt)) + 10 * len(r.findall(head)) + 20 * bool(r.search(str(f.relative_to(DOCS))))
        if score:
            summ = (re.search(r'^summary:\s*"?(.*?)"?$', head, re.M) or re.search(r"^title:\s*(.*)$", head, re.M))
            res.append((score, f, summ.group(1) if summ else ""))
    res.sort(key=lambda x: -x[0])
    for s, f, summ in res[:n]:
        print(f"{f.relative_to(DOCS)}  ({s})  {summ[:110]}")
    print(f"(docs root: {DOCS}; read with sed -n or grep -n, they are long)")


# ---------------------------------------------------------------- backup / diff / log
def backup(what, files):
    what = re.sub(r"[^A-Za-z0-9_-]+", "-", what).strip("-") or "change"
    dest = OC_DIR / f"openclaw.json.bak-{datetime.date.today():%Y%m%d}-{what}"
    if dest.exists():
        dest = dest.with_name(dest.name + f"-{datetime.datetime.now():%H%M%S}")
    shutil.copy2(CONFIG, dest)
    print(f"{CONFIG} -> {dest}")
    print(f"undo config: cp -p {dest} {CONFIG} && openclaw config validate")
    for f in files:
        b = rig.backup(f)
        print(f"{f} -> {b}\nundo file: cp -p {b} {f}")


def diff(old=None, new=None):
    if old is None:
        baks = sorted(OC_DIR.glob("openclaw.json.bak-*"), key=lambda p: p.stat().st_mtime)
        if not baks:
            sys.exit("no ~/.openclaw/openclaw.json.bak-* yet - give OLD explicitly")
        old = baks[-1]
    old, new = pathlib.Path(old), pathlib.Path(new or CONFIG)
    print(f"--- {old}\n+++ {new}")
    if old.read_bytes() == new.read_bytes():
        print("byte-identical")
        return
    a, b = flatten(redact(load(old))), flatten(redact(load(new)))
    if a == b:
        print("JSON-equivalent (only formatting/key order differs)")
        return
    for k in sorted(set(a) | set(b)):
        if k not in b:
            print(f"- {k} = {json.dumps(a[k])[:200]}")
        elif k not in a:
            print(f"+ {k} = {json.dumps(b[k])[:200]}")
        elif a[k] != b[k]:
            print(f"~ {k}: {json.dumps(a[k])[:120]} -> {json.dumps(b[k])[:120]}")


def test(agent, message, model=None, timeout=900):
    key = f"agent:{agent}:oc-test-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    args = ["agent", "--agent", agent, "--session-key", key, "--json", "--timeout", str(timeout), "--message", message]
    if model:
        args += ["--model", model]
    print(f"session {key}; running (up to {timeout} s)...", flush=True)
    rc, out, err = oc(*args, timeout=timeout + 60)
    CACHE.mkdir(parents=True, exist_ok=True)
    raw = CACHE / f"test-{key.rsplit(':', 1)[-1]}.json"
    raw.write_text(out)
    try:
        d = json.loads(out)
    except ValueError:
        sys.exit(f"rc {rc}, no JSON. stderr: {err[-1500:]}")
    meta = d.get("result", {}).get("meta", {})
    tr, sp = meta.get("executionTrace", {}), meta.get("systemPromptReport", {})
    print(f"status {d.get('status')} ({d.get('summary')}), {meta.get('durationMs')} ms, stop {meta.get('stopReason')}")
    print(f"model {tr.get('winnerProvider')}/{tr.get('winnerModel')}, fallback used: {tr.get('fallbackUsed')}, "
          f"attempts {[(a.get('model'), a.get('result')) for a in tr.get('attempts', [])]}")
    print(f"workspace {sp.get('workspaceDir')}: " + ", ".join(
        f"{f['name']}{' MISSING' if f.get('missing') else ''}{' TRUNCATED' if f.get('truncated') else ''}"
        for f in sp.get("injectedWorkspaceFiles", [])))
    print(f"skills ({sp.get('skills', {}).get('promptChars')} chars): "
          + ", ".join(s["name"] for s in sp.get("skills", {}).get("entries", [])))
    print("tools: " + ", ".join(t["name"] for t in sp.get("tools", {}).get("entries", [])))
    print(f"reply: {(meta.get('finalAssistantVisibleText') or '')[:1500]}")
    print(f"(full JSON: {raw}; rc {rc})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd, rest = a[0], a[1:]
    if cmd == "state":
        state()
    elif cmd == "schema":
        show(rest[0] if rest else "")
    elif cmd == "find" and rest:
        find(rest[0], int(rest[1]) if len(rest) > 1 else 40)
    elif cmd == "docs" and rest:
        docs(rest[0], int(rest[1]) if len(rest) > 1 else 12)
    elif cmd == "backup" and rest:
        backup(rest[0], rest[1:])
    elif cmd == "diff":
        diff(*rest[:2])
    elif cmd == "test" and len(rest) >= 2:
        opt = dict(zip(rest[2::2], rest[3::2]))
        test(rest[0], rest[1], opt.get("--model"), int(opt.get("--timeout", 900)))
    elif cmd == "log" and rest:
        print(rig.journal("update-openclaw-config", " ".join(rest)))
    else:
        sys.exit(__doc__)
