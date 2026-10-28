#!/usr/bin/env python3
"""What is this model file and how should it run on this rig?  (reads headers only - seconds, no GPU)

  model_facts.py PATH [--ctx 131072] [--json]
     PATH = a .gguf file (first shard for split models), a folder with .gguf files, or a safetensors folder
            (config.json) for vLLM.

Prints: architecture, size, layers, attention layout, experts, native context, MTP/draft head, vision projector
next to it, and a GPU plan: how many R9700 cards (32 GB) the weights + KV cache need at several context sizes
(f16 and q8_0 KV). KV estimate = 2 x layers x kv_heads x head_dim x bytes per token; it OVERESTIMATES models with
sliding-window or linear-attention layers (Gemma, Qwen3.x-Next/Flash-Next, gpt-oss) - for those trust a real load.
"""
import glob, json, os, pathlib, re, struct, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import rig

T = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
FILE_TYPES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1", 10: "Q2_K", 11: "Q3_K_S",
              12: "Q3_K_M", 13: "Q3_K_L", 14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M", 18: "Q6_K",
              19: "IQ2_XXS", 20: "IQ2_XS", 21: "Q2_K_S", 22: "IQ3_XS", 23: "IQ3_XXS", 24: "IQ1_S", 25: "IQ4_NL",
              26: "IQ3_S", 27: "IQ3_M", 28: "IQ2_S", 29: "IQ2_M", 30: "IQ4_XS", 31: "IQ1_M", 32: "BF16",
              36: "TQ1_0", 37: "TQ2_0", 38: "MXFP4_MOE"}


def read_kv(path, skip_arrays_over=64):
    """GGUF key/values (arrays longer than skip_arrays_over are summarised as their length)."""
    kv = {}
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise SystemExit(f"{path}: not a GGUF file")
        ver, = struct.unpack("<I", f.read(4))
        n_t, n_kv = struct.unpack("<QQ", f.read(16))

        def s():
            n, = struct.unpack("<Q", f.read(8))
            return f.read(n).decode("utf-8", "replace")

        def val(t):
            if t == 8:
                return s()
            if t == 9:
                at, n = struct.unpack("<IQ", f.read(12))
                if at == 8:
                    items = [s() for _ in range(n)]
                else:
                    size = struct.calcsize(T[at])
                    raw = f.read(size * n)
                    items = list(struct.unpack("<" + T[at][1] * n, raw)) if n <= skip_arrays_over else None
                return items if items is not None and n <= skip_arrays_over else f"<array of {n}>"
            return struct.unpack(T[t], f.read(struct.calcsize(T[t])))[0]

        for _ in range(n_kv):
            k = s()
            t, = struct.unpack("<I", f.read(4))
            kv[k] = val(t)
    kv["_tensors"] = n_t
    kv["_version"] = ver
    return kv


def shards(path):
    m = re.match(r"(.*)-(\d{5})-of-(\d{5})\.gguf$", path)
    return sorted(glob.glob(f"{m.group(1)}-*-of-{m.group(3)}.gguf")) if m else [path]


def gguf_facts(path):
    kv = read_kv(path)
    a = kv.get("general.architecture", "?")
    g = lambda k, d=None: kv.get(f"{a}.{k}", d)
    files = shards(path)
    size = sum(os.path.getsize(p) for p in files)
    heads = g("attention.head_count")
    heads = max(heads) if isinstance(heads, list) else heads
    layers = g("block_count")
    emb = g("embedding_length")
    kvh = g("attention.head_count_kv") or heads
    kvh_l = kvh if isinstance(kvh, list) else [kvh] * (layers or 0)
    k_full = g("attention.key_length") or (emb // heads if emb and heads else 0)
    v_full = g("attention.value_length") or k_full
    swa = g("attention.sliding_window")
    pattern = g("attention.sliding_window_pattern")
    pattern = pattern if isinstance(pattern, list) else [False] * (layers or 0)
    interval = g("full_attention_interval")
    kv_layers = []      # (kv_heads, k_dim, v_dim, window or None) per layer that keeps a KV cache
    for i in range(layers or 0):
        if interval and (i + 1) % interval:
            continue    # linear-attention / SSM layer: fixed-size state, no per-token KV
        if i < len(kvh_l) and kvh_l[i] == 0:
            continue
        is_swa = bool(swa) and i < len(pattern) and pattern[i]
        kv_layers.append((kvh_l[i] if i < len(kvh_l) else kvh_l[-1],
                          (g("attention.key_length_swa") or k_full) if is_swa else k_full,
                          (g("attention.value_length_swa") or v_full) if is_swa else v_full,
                          swa if is_swa else None))
    folder = pathlib.Path(path).parent
    around = list(folder.glob("*.gguf")) + list(folder.parent.glob("*.gguf")) + list(folder.glob("*/*.gguf"))
    mmproj = sorted({str(p) for p in around if "mmproj" in p.name.lower()})
    drafts = sorted({str(p) for p in around if re.search(r"(?i)(mtp|nextn|draft|eagle|dflash)", p.name) and "mmproj" not in p.name.lower()})
    return {
        "file": path, "shards": len(files), "size_gib": size / 2**30, "gguf_version": kv["_version"],
        "name": kv.get("general.name"), "arch": a, "size_label": kv.get("general.size_label"),
        "quant": FILE_TYPES.get(kv.get("general.file_type"), kv.get("general.file_type")),
        "native_ctx": g("context_length"), "layers": layers, "kv_cache_layers": len(kv_layers),
        "heads": heads, "kv_heads": kvh if not isinstance(kvh, list) else sorted(set(kvh)), "head_dim": k_full,
        "embedding": emb, "full_attention_interval": interval, "_kv_layers": kv_layers,
        "experts": g("expert_count"), "experts_used": g("expert_used_count"),
        "sliding_window": g("attention.sliding_window"), "mtp_layers_in_file": g("nextn_predict_layers"),
        "has_chat_template": "tokenizer.chat_template" in kv,
        "vision_projectors_nearby": mmproj, "draft_heads_nearby": drafts,
    }


def st_facts(folder):
    cfg = json.load(open(os.path.join(folder, "config.json")))
    tc = cfg.get("text_config", cfg)
    size = sum(os.path.getsize(p) for p in glob.glob(os.path.join(folder, "*.safetensors")))
    heads = tc.get("num_attention_heads")
    return {"file": folder, "size_gib": size / 2**30, "arch": (cfg.get("architectures") or ["?"])[0],
            "quant": (cfg.get("quantization_config") or {}).get("quant_method", cfg.get("torch_dtype")),
            "native_ctx": tc.get("max_position_embeddings"), "layers": tc.get("num_hidden_layers"),
            "attention_layers": (sum(1 for t in tc["layer_types"] if "full" in t or t == "attention") if tc.get("layer_types")
                                 else tc["num_hidden_layers"] // tc["full_attention_interval"] if tc.get("full_attention_interval")
                                 else tc.get("num_hidden_layers")), "heads": heads,
            "kv_heads": tc.get("num_key_value_heads", heads),
            "head_dim": tc.get("head_dim") or (tc.get("hidden_size", 0) // heads if heads else None),
            "experts": tc.get("num_experts") or tc.get("n_routed_experts"),
            "experts_used": tc.get("num_experts_per_tok"), "vision": "vision_config" in cfg,
            "mtp_layers_in_file": tc.get("num_nextn_predict_layers") or tc.get("mtp_num_hidden_layers"),
            "engine_hint": "vLLM (Radiance fork, ~/.config/llama-swap/vllm/)"}


def plan(f, extra_ctx=None):
    lines = []
    w = f["size_gib"] + sum(os.path.getsize(p) / 2**30 for p in f.get("vision_projectors_nearby", [])[:1])
    kvl = f.get("_kv_layers")
    if kvl is None and f.get("attention_layers") and f.get("kv_heads") and f.get("head_dim"):
        kvl = [(f["kv_heads"], f["head_dim"], f["head_dim"], None)] * f["attention_layers"]

    def kv_gb(ctx, nbytes):
        return sum(h * (k + v) * nbytes * (min(ctx, win) if win else ctx) for h, k, v, win in (kvl or [])) / 2**30
    ctxs = sorted({c for c in (extra_ctx, f.get("native_ctx"), 262144, 131072, 65536, 32768) if c and c <= (f.get("native_ctx") or 10**9)}, reverse=True)
    lines.append(f"weights (+1st mmproj) {w:.1f} GiB; KV cache for 32k tokens: f16 {kv_gb(32768, 2):.1f} GiB"
                 if kvl else f"weights {w:.1f} GiB; KV unknown (no attention metadata)")
    lines.append("ctx        KV f16     cards(f16)  KV q8_0    cards(q8_0)   [per card: 31.3 GiB usable, ~1.5 GiB compute buffers]")
    for c in ctxs:
        row = f"{c:>7}"
        for k in ("f16", "q8_0"):
            kvgb = kv_gb(c, 2 if k == "f16" else 1.0625)
            cards = next((n for n in (1, 2, 3, 4) if (w + kvgb) / n + 1.5 <= 31.3), None)
            row += f"   {kvgb:6.1f} GiB  {str(cards or '>4'):>8}"
        lines.append(row)
    lines.append("estimate: sliding-window and linear-attention layers are accounted for; compute buffers, the vision "
                 "projector's work memory and engine quirks are not - confirm with a real load (smoke.py) and amd-smi.")
    return lines


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    p = os.path.expanduser(a[0])
    ctx = int(a[a.index("--ctx") + 1]) if "--ctx" in a else None
    if os.path.isdir(p):
        if os.path.isfile(os.path.join(p, "config.json")) and glob.glob(os.path.join(p, "*.safetensors")):
            facts = st_facts(p)
        else:
            gg = sorted(x for x in glob.glob(os.path.join(p, "**", "*.gguf"), recursive=True)
                        if not re.search(r"(?i)mmproj|mtp|draft|-0000[2-9]-of-|-000[1-9]\d-of-", os.path.basename(x)))
            if not gg:
                sys.exit(f"no model .gguf or safetensors+config.json in {p}")
            if len(gg) > 1:
                print("several weight files found, using the first; pass the file you mean:\n  " + "\n  ".join(gg))
            facts = gguf_facts(gg[0])
    else:
        facts = gguf_facts(p)
    if "--json" in a:
        print(json.dumps({k: v for k, v in facts.items() if not k.startswith("_")}, indent=1, default=str))
        sys.exit()
    for k, v in facts.items():
        if v not in (None, [], "") and not k.startswith("_"):
            print(f"{k:26} {round(v, 2) if isinstance(v, float) else v}")
    print()
    print("\n".join(plan(facts, ctx)))
    free = rig.vram()
    if free:
        print("\nVRAM now: " + ", ".join(f"GPU{g['gpu']} {g['used_gb']:.1f}/{g['total_gb']:.0f} GiB" for g in free)
              + f"; RAM available {rig.ram_gb()['available']:.0f} GB; running in llama-swap: {rig.running()}")
