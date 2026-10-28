#!/usr/bin/env python3
"""Plan, start and watch a model download into ~/models (resumable, runs in the background).

  download.py plan   REPO --include "PATTERN" [--include ...] [--dest DIR]   size + disk check, nothing downloaded
  download.py start  REPO --include "PATTERN" [--include ...] [--dest DIR]   same check, then starts `hf download`
  download.py status [DIR]                                                   progress of running/finished downloads

Rules (this rig): weights go to ~/models/<model-slug>/ (GGUF quants in a sub-folder named after the quant when a repo
has several, e.g. ~/models/gemma-4-26b-a4b/). After the download at least 100 GB and 10 % of /home must stay free.
The download runs detached (nohup) and survives the chat; the Wi-Fi does ~50 MB/s, so 100 GB takes ~35 min.
Re-running `start` with the same arguments resumes (hf skips finished files). Without --include the whole repo is
downloaded (right for vLLM safetensors repos, wrong for GGUF repos with many quants).
"""
import fnmatch, json, os, pathlib, re, subprocess, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import hf, rig

MIN_FREE_GB, MIN_FREE_FRAC = 100, 0.10
STATUS_DIR = rig.STATE / "downloads"


def slug(repo):
    name = repo.split("/")[-1]
    name = re.sub(r"(?i)[-_.](gguf|fp8|awq|gptq|mlx|bf16|instruct-gguf)$", "", name)
    return name.lower()


def parse(a):
    repo = a[0]
    inc = [a[i + 1] for i, x in enumerate(a) if x == "--include"]
    dest = next((a[i + 1] for i, x in enumerate(a) if x == "--dest"), None)
    dest = pathlib.Path(os.path.expanduser(dest)) if dest else rig.MODELS / slug(repo)
    return repo, inc, dest


def plan(repo, inc, dest):
    files = hf.tree(repo)
    pick = [f for f in files if not inc or any(fnmatch.fnmatch(f["path"], p) for p in inc)]
    if not pick:
        sys.exit(f"nothing matches {inc} in {repo}; list files with: hf_find.py files {repo}")
    total = sum(f["size"] for f in pick)
    have = sum((dest / f["path"]).stat().st_size for f in pick if (dest / f["path"]).is_file())
    need = max(total - have, 0)
    free, size = rig.disk_free_gb()
    after = free - need / 1e9
    print(f"repo:        {repo}")
    print(f"files:       {len(pick)} ({', '.join(f['path'] for f in pick[:6])}{' ...' if len(pick) > 6 else ''})")
    print(f"size:        {rig.human(total)}  (already on disk: {rig.human(have)}, to download: {rig.human(need)})")
    print(f"destination: {dest}")
    print(f"disk /home:  {free:.0f} GB free now, {after:.0f} GB after ({after / size * 100:.0f} %)")
    print(f"time:        ~{need / 50e6 / 60:.0f} min at ~50 MB/s (Wi-Fi)")
    ok = after >= MIN_FREE_GB and after / size >= MIN_FREE_FRAC
    if not ok:
        print(f"REFUSED: would leave less than {MIN_FREE_GB} GB / {MIN_FREE_FRAC:.0%} free. Free space first "
              f"(list big unused model folders: du -sh ~/models/* | sort -h) and ask the user what to delete.")
    gated = hf.info(repo).get("gated")
    if gated:
        print("GATED repo: the account michal-konik must have accepted the licence on the model page, else 403.")
    return ok, pick, total


def start(repo, inc, dest):
    ok, pick, total = plan(repo, inc, dest)
    if not ok:
        sys.exit(2)
    dest.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    log = dest / "download.log"
    cmd = ["hf", "download", repo, "--local-dir", str(dest)] + sum((["--include", p] for p in inc), [])
    env = dict(os.environ, HF_HUB_ENABLE_HF_TRANSFER="0")
    p = subprocess.Popen(["nohup"] + cmd, stdout=open(log, "a"), stderr=subprocess.STDOUT, env=env,
                         start_new_session=True)
    st = {"repo": repo, "include": inc, "dest": str(dest), "bytes": total, "pid": p.pid, "log": str(log),
          "started": time.time(), "files": [f["path"] for f in pick]}
    (STATUS_DIR / (slug(repo) + ".json")).write_text(json.dumps(st, indent=1))
    rig.journal("download-llm", f"started {repo} {inc} -> {dest} ({rig.human(total)}), pid {p.pid}")
    print(f"\nSTARTED pid {p.pid}: {' '.join(cmd)}\nlog: {log}\nwatch: download.py status {dest}")


def du(path):
    tot = 0
    for root, _, fs in os.walk(path):
        for f in fs:
            try:
                tot += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return tot


def status(dest=None):
    sts = [json.loads(p.read_text()) for p in sorted(STATUS_DIR.glob("*.json"))] if STATUS_DIR.is_dir() else []
    if dest:
        sts = [s for s in sts if pathlib.Path(s["dest"]) == pathlib.Path(os.path.expanduser(dest))]
    if not sts:
        print("no downloads recorded")
    for s in sts:
        alive = pathlib.Path(f"/proc/{s['pid']}").exists()
        have = du(s["dest"])  # includes the .cache/huggingface partial files hf writes while downloading
        el = time.time() - s["started"]
        rate = have / el if el > 0 else 0
        done = all((pathlib.Path(s["dest"]) / f).is_file() for f in s["files"])
        state = "RUNNING" if alive else ("DONE" if done else "STOPPED (incomplete - re-run start to resume)")
        eta = (s["bytes"] - have) / rate / 60 if alive and rate > 0 else 0
        print(f"{state:8} {s['repo']} -> {s['dest']}\n   {rig.human(have)} of {rig.human(s['bytes'])}"
              f" ({have / max(s['bytes'], 1) * 100:.0f} %), avg {rate / 1e6:.0f} MB/s"
              f"{f', ETA ~{eta:.0f} min' if alive else ''}; log {s['log']}")
        if not alive:
            tail = subprocess.run(["tail", "-n", "3", s["log"]], capture_output=True, text=True).stdout.strip()
            if tail:
                print("   last log lines: " + tail.replace("\n", " | ")[-400:])


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("plan", "start", "status"):
        sys.exit(__doc__)
    if a[0] == "status":
        status(a[1] if len(a) > 1 else None)
    elif len(a) < 2:
        sys.exit(__doc__)
    elif a[0] == "plan":
        ok, _, _ = plan(*parse(a[1:]))
        sys.exit(0 if ok else 2)
    else:
        start(*parse(a[1:]))
