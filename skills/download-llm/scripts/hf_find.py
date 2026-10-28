#!/usr/bin/env python3
"""Search Hugging Face for a model and show what is downloadable.

  hf_find.py search "qwen3.8 flash" [--gguf] [--limit 15]   candidate repos, most downloaded first
  hf_find.py files  unsloth/Gemma-4-26B-A4B-it-GGUF          files grouped by quant, with total sizes

`files` groups GGUF shards into one row per quant (sum of all parts), and lists vision projectors (mmproj) and
draft/MTP heads separately, because those are extra downloads a model on this rig usually wants.
"""
import pathlib, sys, collections, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import hf, rig


def cmd_search(q, gguf, limit):
    rows = hf.search(q, limit=limit, gguf=gguf)
    if not rows:
        print("no repos found - try fewer words, the family name only, or without --gguf")
        return
    print(f"{'repo':60} {'downloads':>10} {'likes':>6}  updated     formats / notes")
    for r in rows:
        tags = set(r.get("tags") or [])
        fmt = [t for t in ("gguf", "safetensors", "mlx", "onnx") if t in tags]
        notes = []
        if r.get("gated"):
            notes.append("GATED (accept on the model page, account michal-konik)")
        if any(t.startswith("base_model:quantized:") for t in tags):
            notes.append("quantized copy")
        upd = (r.get("lastModified") or "")[:10]
        print(f"{r['id'][:60]:60} {r.get('downloads', 0):>10} {r.get('likes', 0):>6}  {upd}  {','.join(fmt)} {'; '.join(notes)}")


def cmd_files(repo):
    meta = hf.info(repo)
    files = hf.tree(repo)
    print(f"{repo}  (updated {meta.get('lastModified', '')[:10]}, gated={meta.get('gated', False)}, "
          f"license={(meta.get('cardData') or {}).get('license', '?')})")
    groups = collections.defaultdict(lambda: {"size": 0, "files": []})
    for f in files:
        kind = hf.classify(f["path"])
        key = (kind, hf.quant_of(f["path"]) if kind != "other" else "")
        if kind == "other" and f["size"] < 50e6:
            continue  # config/tokenizer/readme - downloaded automatically by include patterns that need them
        folder = f["path"].rsplit("/", 1)[0] + "/" if "/" in f["path"] else ""
        key = key + (folder,)
        groups[key]["size"] += f["size"]
        groups[key]["files"].append(f["path"])
    free, total = rig.disk_free_gb()
    print(f"disk: {free:.0f} GB free of {total:.0f} GB on /home (keep >= 100 GB free)\n")
    print(f"{'kind':28} {'quant':16} {'size':>10}  files  include pattern")
    for (kind, quant, folder), g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[1]["size"])):
        first = g["files"][0]
        if len(g["files"]) == 1:
            pattern = first
        elif kind == "gguf weights" and quant != "?":
            pattern = folder + "*" + quant + "*"
        else:
            pattern = folder + "*"
        print(f"{kind:28} {quant:16} {rig.human(g['size']):>10}  {len(g['files']):5}  {pattern}")
    st = sum(f["size"] for f in files if f["path"].endswith(".safetensors"))
    if st:
        print(f"\nsafetensors total: {rig.human(st)} (vLLM/transformers format; for vLLM download the whole repo)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("search", "files"):
        sys.exit(__doc__)
    if a[0] == "search":
        limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 15
        words = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] != "--limit"]
        cmd_search(" ".join(words), "--gguf" in a, limit)
    else:
        cmd_files(a[1])
