#!/usr/bin/env python3
"""Everything about one llama-swap model's current setup, in one page.  model_report.py MODEL

MODEL = id, alias or unique part of the name. Shows: the entry with its comments, every flag explained, the engine
build/image and its age vs upstream, the model files (size, quant, arch, native context, MTP, vision), measured
numbers recorded in comments/description and saved benchmarks, whether it is running, and a checklist of the
optimisation levers that are NOT used yet. Read-only; no model is loaded.
"""
import json, os, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import rig

BIN = pathlib.Path(__file__).resolve().parent


def run(cmd, timeout=30):
    return rig.sh(cmd, timeout)[1]


def section(t):
    print(f"\n=== {t}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    mid = rig.resolve_model(sys.argv[1])
    m = rig.models()[mid]
    cmd = m["cmd"]
    eng = rig.engine(cmd)
    section(f"{mid}  ({eng}, GPUs {rig.gpus_of(m)}, running: {mid in rig.running()})")
    print(run(f"python3 {BIN}/ls_entry.py show {mid}"))
    section("flags explained")
    print(run(f"python3 {BIN}/ls_entry.py explain {mid}"))

    section("engine version")
    if eng.startswith("llama.cpp"):
        binary = cmd.split()[0]
        root = binary.split("/build/")[0]
        local = run(f"git -C {root} log -1 --format='%h %cs %s'")
        up = run("git ls-remote https://github.com/ggml-org/llama.cpp refs/heads/master", 20).split()[:1]
        sha = local.split()[0] if local else "?"
        print(f"build {root}: {local}")
        print(f"upstream master now: {up[0][:9] if up else '?'}; what changed since this build (fetch it): "
              f"https://github.com/ggml-org/llama.cpp/compare/{sha}...master  and releases: https://github.com/ggml-org/llama.cpp/releases")
        print("other builds here: " + run("ls -d ~/llama.cpp*/build/bin/llama-server | sed 's#/build/bin/llama-server##' | tr '\\n' ' '"))
    else:
        comp = re.search(r"(\S+\.compose\.yml)", cmd)
        if comp:
            img = run(f"grep -m1 'image:' {comp.group(1)} | awk '{{print $2}}'")
            print(f"compose {comp.group(1)}; image {img}; created {run(f'docker image inspect -f {{{{.Created}}}} {img}')[:10]}")
            print("check newer tags: https://hub.docker.com/r/" + img.split(':')[0] + "/tags")

    section("model files")
    paths = re.findall(r"(?:^|\s)(-m|--model|--mmproj|-md|--model-draft)\s+(\S+)", cmd)
    main_files = {p for f, p in paths if f in ("-m", "--model")}
    paths = [p for _, p in paths]
    md = re.search(r"MODELDIR=(\S+)", cmd)
    if md:
        paths.append(md.group(1))
    if eng == "vllm":
        paths += re.findall(r"(/home/\S+/models/\S+)", run(f"grep -E 'models|MODEL' {re.search(r'(\S+compose.yml)', cmd).group(1)}"))
    for p in paths:
        p = os.path.expanduser(p)
        size = run(f"du -sh {p} 2>/dev/null | cut -f1")
        print(f"- {p}  ({size})")
        if p in main_files:
            print("  " + run(f"python3 {BIN}/model_facts.py {p}").replace("\n", "\n  ")[:3000])

    section("measured (from comments/description) and saved benchmarks")
    entry = run(f"python3 {BIN}/ls_entry.py show {mid}")
    for line in (entry + "\n" + m.get("description", "")).splitlines():
        if re.search(r"tok/s|tok/s|tg\d|zmierzone|measured|bench", line, re.I):
            print("  " + line.strip()[:160])
    benches = sorted((rig.STATE / "bench").glob(f"{mid}-*.json")) if (rig.STATE / "bench").is_dir() else []
    print("  saved runs: " + (", ".join(b.name for b in benches[-5:]) or "none (bench.py run <id> to create one)"))

    section("levers not used yet (candidates to research - not all apply)")
    checks = [
        ("--mmproj" not in cmd and eng.startswith("llama.cpp"), "no vision projector (if the model has vision: --mmproj)"),
        ("--spec-type" not in cmd and "-md " not in cmd and eng.startswith("llama.cpp"), "no speculative decoding (MTP head / ngram-mod)"),
        ("--ubatch-size" not in cmd and eng.startswith("llama.cpp"), "ubatch not tuned (default 512 was never best here)"),
        ("--parallel" not in cmd and eng.startswith("llama.cpp"), "single slot (--parallel N --kv-unified for agents)"),
        (eng == "llama.cpp-rocm" and len(rig.gpus_of(m)) == 1, "1-card model on ROCm: Vulkan build is usually faster for MoE"),
        ("--temp" not in cmd and eng.startswith("llama.cpp"), "no sampling flags: check the vendor's recommended sampling"),
        (not any(mid in (g.get("members") or []) for g in rig.groups().values()), "not in a group: loading it unloads everything else"),
    ]
    for cond, text in checks:
        if cond:
            print("  - " + text)
    print("\nNext: research online (model card, engine release notes, newer quants/drafts), then propose changes.")


if __name__ == "__main__":
    main()
