#!/usr/bin/env python3
"""Safely read and change model entries in ~/.config/llama-swap/config.yaml (comments are preserved).

  ls_entry.py list                          ids, engine, GPUs, ctx, running or not
  ls_entry.py show    ID                    the entry exactly as written (with its comment block)
  ls_entry.py explain ID                    every flag of the entry with what it does
  ls_entry.py add     ID FILE [--dry-run]   insert FILE (YAML for ONE entry, first line `  "ID":`) before `groups:`
  ls_entry.py replace ID FILE [--dry-run]   replace the entry (from its key line to its end) with FILE
  ls_entry.py patch   ID "OLD" "NEW" [--dry-run]   replace text that occurs exactly once inside the entry
  ls_entry.py remove  ID [--dry-run]        delete the entry (and its comment block)
  ls_entry.py rollback BACKUP_FILE          put a backup back (the current file is backed up first)

Every change: backup to ~/.local/state/rig-skills/backups/<time>/, YAML validated before saving, written atomically,
diff printed, line added to ~/.local/state/rig-skills/journal.log. llama-swap watches the file and reloads it on
save; a RUNNING model whose entry changed is restarted - if that is the model running this chat, the answer ends.
"""
import difflib, os, pathlib, re, shlex, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import rig

KEY = re.compile(r'^  ("?)([^"\s#:][^":]*)\1:\s*(#.*)?$')

FLAGS = {
    "-m": "model weights file", "--model": "model weights file",
    "--mmproj": "vision projector: lets the model read images (+~1 GB VRAM)",
    "-md": "draft model / MTP head for speculative decoding", "--model-draft": "draft model for speculative decoding",
    "--spec-type": "speculative decoding kind (draft-mtp = model's own MTP head, ngram-mod = reuse repeated text)",
    "--spec-draft-n-max": "max tokens drafted per step (more = bigger wins on predictable text, more waste on prose)",
    "-ngl": "layers offloaded to GPU (999 = all)", "--n-gpu-layers": "layers offloaded to GPU",
    "--ctx-size": "context window in tokens (shared by all slots when --kv-unified)", "-c": "context window",
    "--parallel": "slots = requests served at the same time", "-np": "parallel slots",
    "--kv-unified": "one KV pool shared by all slots (a single long chat can use the whole context)",
    "--batch-size": "logical batch for prompt processing", "--ubatch-size": "physical batch; tuned per model by measurement (bigger = faster prompt, more VRAM)",
    "-fa": "flash attention (on everywhere here)", "--split-mode": "how a model is spread over GPUs: layer (pipeline) or row/tensor",
    "--tensor-split": "share of the model per GPU, comma-separated (llama-bench uses slashes!)",
    "--cache-type-k": "K cache type (f16 default; q8_0 halves KV memory, small quality cost)",
    "--cache-type-v": "V cache type (needs -fa)", "--load-mode": "how weights are read (dio = direct I/O, fast for huge files)",
    "--temp": "sampling temperature (vendor recommendation)", "--top-p": "nucleus sampling", "--top-k": "top-k sampling",
    "--min-p": "min-p sampling", "--presence-penalty": "penalise repeats", "--jinja": "use the model's chat template (needed for tools)",
    "--agent": "llama.cpp built-in agent tools in the web UI", "--tools": "which built-in tools the web UI may use",
    "--mcp-servers-config": "MCP servers for the web UI (rig-web: web search, fetch, sudo approval)",
    "--chat-template-file": "custom chat template (e.g. Bielik tools)", "--ui-config-file": "web UI defaults (system prompt) written by sync_prompts.py",
    "--cors-origins": "web origins allowed to call the server", "--port": "port (llama-swap fills ${PORT})",
    "--no-mmap": "read weights into RAM instead of mapping", "--mlock": "pin weights in RAM (avoid: RAM is the limit here)",
    "--reasoning-budget": "limit thinking tokens", "--override-tensor": "place given tensors on given devices (e.g. MoE experts on CPU)",
}
ENV = {"HIP_VISIBLE_DEVICES": "ROCm GPUs this model may use (0-3; 4 = iGPU, never)",
       "GGML_VK_VISIBLE_DEVICES": "Vulkan GPUs this model may use (0-3; 4 = iGPU, never)"}
KEYS = {"ttl": "seconds idle before llama-swap unloads it", "proxy": "where llama-swap forwards requests (Docker engines)",
        "checkEndpoint": "health URL llama-swap waits for", "useModelName": "model name sent to the engine",
        "concurrencyLimit": "max parallel requests llama-swap lets through (default 10)", "aliases": "other names for the model",
        "name": "display name in UIs", "description": "shown in UIs and in the model's own system prompt"}
COMPOSE = {"PORT": "port llama-swap assigns", "GPUS": "GPUs for the container", "TP": "tensor-parallel size (cards)", "SEQS": "max parallel sequences",
           "KVDT": "KV cache dtype", "MAXLEN": "context length", "WIRE": "radiance TP wire format (exact = lossless)",
           "NGRAM": "radiance n-gram table placement", "HOSTPOOL": "radiance pinned host pool per card (MiB, counts against RAM)",
           "MODELDIR": "model folder", "RADFILE": ".rad weights file", "NAME": "container name", "CHAT_MODEL": "served model name"}


def lines():
    return rig.LS_CONFIG.read_text().splitlines(keepends=True)


def bounds(ls, mid):
    """(comment_start, key_line, end) of entry `mid` inside models:, end exclusive."""
    try:
        m0 = next(i for i, l in enumerate(ls) if l.rstrip() == "models:")
    except StopIteration:
        sys.exit("no 'models:' section")
    m1 = next((i for i in range(m0 + 1, len(ls)) if re.match(r"^\S", ls[i]) and not ls[i].startswith("#")), len(ls))
    keys = [i for i in range(m0 + 1, m1) if KEY.match(ls[i].rstrip("\n"))]
    names = {KEY.match(ls[i].rstrip("\n")).group(2): i for i in keys}
    if mid not in names:
        return None, m0, m1, keys
    k = names[mid]
    nxt = next((i for i in keys if i > k), m1)
    end = nxt
    while end - 1 > k and (ls[end - 1].strip() == "" or re.match(r"^\s*#", ls[end - 1])):
        end -= 1          # the comment block right above the next key belongs to the next entry
    start = k
    while start - 1 > m0 and re.match(r"^\s*#", ls[start - 1]) and not ls[start - 1].startswith("# "):
        start -= 1
    return (start, k, end), m0, m1, keys


def save(new_text, why):
    import yaml
    try:
        cfg = yaml.safe_load(new_text)
        assert isinstance(cfg.get("models"), dict)
        for mid, m in cfg["models"].items():
            assert isinstance(m, dict) and "cmd" in m, f"entry {mid} has no cmd"
    except Exception as e:
        sys.exit(f"NOT SAVED - result is not a valid llama-swap config: {e}")
    old = rig.LS_CONFIG.read_text()
    diff = "".join(difflib.unified_diff(old.splitlines(True), new_text.splitlines(True), "config.yaml (before)", "config.yaml (after)"))
    print(diff or "(no change)")
    if "--dry-run" in sys.argv or not diff:
        print("dry run - nothing written" if diff else "")
        return
    bk = rig.backup(rig.LS_CONFIG)
    fd, tmp = tempfile.mkstemp(dir=rig.LS_DIR, prefix=".config.yaml.")
    with os.fdopen(fd, "w") as f:
        f.write(new_text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, rig.LS_CONFIG)
    print(f"\nSAVED. backup: {bk}\nundo: python3 {__file__} rollback {bk}")
    print(rig.journal("ls_entry", f"{why}; backup {bk}"))
    print("next: llama-swap reloads in ~1 s; then run sync_prompts.py so the UIs and prompts match:\n"
          f"  python3 {rig.SYNC_PROMPTS}")


def read_block(path):
    t = pathlib.Path(path).read_text()
    if not t.endswith("\n"):
        t += "\n"
    first = next(l for l in t.splitlines() if l.strip() and not l.strip().startswith("#"))
    if not KEY.match(first):
        sys.exit(f'{path}: the first non-comment line must be the entry key indented by 2 spaces, e.g.  "my-model":')
    return t, KEY.match(first).group(2)


def explain(mid):
    m = rig.models()[mid]
    print(f"{mid}: engine {rig.engine(m['cmd'])}, GPUs {rig.gpus_of(m)}")
    for k, v in m.items():
        if k not in ("cmd", "env"):
            print(f"  {k}: {str(v)[:110]}  -- {KEYS.get(k, '')}")
    for e in m.get("env") or []:
        k = e.split("=")[0]
        print(f"  env {e}  -- {ENV.get(k, '')}")
    toks = shlex.split(m["cmd"].replace("\n", " "))
    print(f"  binary/wrapper: {toks[0]}")
    i = 1
    while i < len(toks):
        t = toks[i]
        if t.startswith("-"):
            val = toks[i + 1] if i + 1 < len(toks) and not toks[i + 1].startswith("-") else ""
            print(f"  {t} {val[:90]}  -- {FLAGS.get(t, '?')}")
            i += 2 if val else 1
        else:
            k = t.split("=")[0]
            print(f"  {t[:100]}  -- {COMPOSE.get(k, 'compose file' if t.endswith('.yml') else '')}")
            i += 1


def main():
    a = [x for x in sys.argv[1:] if x != "--dry-run"]
    if not a:
        sys.exit(__doc__)
    op = a[0]
    ls = lines()
    if op == "list":
        run = rig.running()
        for mid, m in rig.models().items():
            ctx = re.search(r"(?:--ctx-size|-c|MAXLEN=)\s*=?(\d+)", m["cmd"])
            print(f"{mid:34} {rig.engine(m['cmd']):17} GPU {','.join(map(str, rig.gpus_of(m))):8} ctx {ctx.group(1) if ctx else '?':>7}"
                  f"  {'RUNNING' if mid in run else ''}")
        for g, d in rig.groups().items():
            print(f"group {g}: {d}")
        return
    if op == "rollback":
        bk = pathlib.Path(a[1])
        save(bk.read_text(), f"rollback to {bk}")
        return
    mid = a[1]
    b, m0, m1, keys = bounds(ls, mid)
    if op == "show":
        if not b:
            sys.exit(f"no entry {mid}")
        print("".join(ls[b[0]:b[2]]))
    elif op == "explain":
        explain(rig.resolve_model(mid))
    elif op == "add":
        if b:
            sys.exit(f"entry {mid} already exists - use replace")
        block, key = read_block(a[2])
        if key != mid:
            sys.exit(f"FILE defines {key}, not {mid}")
        g = next((i for i in range(m0, len(ls)) if ls[i].startswith("groups:")), m1)
        while g - 1 > m0 and (ls[g - 1].startswith("#") or ls[g - 1].strip() == ""):
            g -= 1        # keep the comment block that introduces groups: together with it
        new = ls[:g] + ["\n", block, "\n"] + ls[g:]
        save("".join(new), f"add entry {mid} from {a[2]}")
    elif op == "replace":
        if not b:
            sys.exit(f"no entry {mid}")
        block, key = read_block(a[2])
        if key != mid:
            sys.exit(f"FILE defines {key}, not {mid}")
        new = ls[:b[1]] + [block] + ls[b[2]:]
        save("".join(new), f"replace entry {mid} from {a[2]}")
    elif op == "patch":
        if not b:
            sys.exit(f"no entry {mid}")
        old, new_s = a[2], a[3]
        body = "".join(ls[b[1]:b[2]])
        n = body.count(old)
        if n != 1:
            sys.exit(f"'{old}' occurs {n} times in entry {mid} (must be exactly 1) - give more context")
        new = "".join(ls[:b[1]]) + body.replace(old, new_s) + "".join(ls[b[2]:])
        save(new, f"patch {mid}: '{old}' -> '{new_s}'")
    elif op == "remove":
        if not b:
            sys.exit(f"no entry {mid}")
        new = ls[:b[0]] + ls[b[2]:]
        txt = "".join(new)
        if re.search(rf'^\s*-\s*"?{re.escape(mid)}"?\s*$', txt, re.M):
            print(f"WARNING: {mid} is still listed in a group - remove it there too (edit groups: by hand)")
        save(txt, f"remove entry {mid}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
