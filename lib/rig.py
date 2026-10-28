"""Shared helpers for the rig skills (import with: sys.path.insert(0, <repo>/lib); import rig).

Everything here is read-only except backup() and journal(). Paths and facts are this machine's:
mkoniu-B850-AI-TOP, 4x Radeon AI PRO R9700 (GPU 0-3, 32 GB each), iGPU = index 4 (never use it),
60 GB RAM (the real limit), models in ~/models, llama-swap on :8080.
"""
import datetime, json, os, pathlib, re, shutil, subprocess, urllib.request

HOME = pathlib.Path.home()
REPO = pathlib.Path(__file__).resolve().parent.parent
LS_DIR = HOME / ".config" / "llama-swap"
LS_CONFIG = LS_DIR / "config.yaml"
LS_URL = "http://127.0.0.1:8080"
MODELS = HOME / "models"
STATE = HOME / ".local" / "state" / "rig-skills"
BACKUPS = STATE / "backups"
JOURNAL = STATE / "journal.log"
SYNC_PROMPTS = LS_DIR / "tools" / "sync_prompts.py"
BENCH = HOME / "Desktop" / "github_repos" / "local-llm-perf-bench" / "server-bench"
PRIVATE_DOCS = HOME / "Desktop" / "github_repos" / "llm-private-education"
R9700 = (0, 1, 2, 3)          # the four real GPUs; index 4 is the iGPU (2 GB) - never put it in *_VISIBLE_DEVICES
VRAM_GB = 32.0                 # per R9700 (31.9 usable)
RAM_GB = 60.0


def sh(cmd, timeout=60):
    """Run a shell command, return (rc, stdout+stderr)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def http_json(url, body=None, timeout=10):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def now():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(path):
    """Copy a file to ~/.local/state/rig-skills/backups/<timestamp>/<flattened path>; return the copy's path."""
    path = pathlib.Path(path)
    dest = BACKUPS / now() / str(path).strip("/").replace("/", "__")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def journal(skill, text):
    """Append one line to the shared change journal (what changed, why, how to undo)."""
    STATE.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {skill}: {' '.join(str(text).split())}\n"
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(line)
    return line.strip()


# ---------------------------------------------------------------- llama-swap
def load_config():
    import yaml
    return yaml.safe_load(LS_CONFIG.read_text())


def models():
    return load_config().get("models", {})


def resolve_model(name):
    """Find a llama-swap model id by id, alias or a unique substring of id/name."""
    ms = models()
    if name in ms:
        return name
    for mid, m in ms.items():
        if name in (m.get("aliases") or []):
            return mid
    hits = [mid for mid, m in ms.items() if name.lower() in (mid + " " + m.get("name", "")).lower()]
    if len(hits) == 1:
        return hits[0]
    raise SystemExit(f"model '{name}' not found or ambiguous {hits}; known ids: {', '.join(ms)}")


def running():
    try:
        return [r.get("model") for r in http_json(LS_URL + "/running").get("running", [])]
    except Exception as e:
        return [f"(llama-swap not reachable: {e})"]


def groups():
    return load_config().get("groups", {}) or {}


def engine(cmd):
    if "radiance/" in cmd:
        return "radiance"
    if "vllm/" in cmd:
        return "vllm"
    if "vulkan" in cmd.split()[0]:
        return "llama.cpp-vulkan"
    return "llama.cpp-rocm"


def gpus_of(m):
    cmd = m["cmd"]
    env = " ".join(m.get("env") or [])
    g = re.search(r"\bGPUS=(\S+)", cmd) or re.search(r"(?:GGML_VK_VISIBLE_DEVICES|HIP_VISIBLE_DEVICES|CUDA_VISIBLE_DEVICES)=(\S+)", env)
    return [int(x) for x in g.group(1).split(",")] if g else list(R9700)


def validate_yaml(path=LS_CONFIG):
    import yaml
    yaml.safe_load(pathlib.Path(path).read_text())
    return True


# ---------------------------------------------------------------- resources
def disk_free_gb(path=MODELS):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / 1e9, st.f_blocks * st.f_frsize / 1e9


def ram_gb():
    info = dict(l.split(":", 1) for l in open("/proc/meminfo"))
    kb = lambda k: int(info[k].split()[0]) / 1e6
    return {"total": kb("MemTotal"), "available": kb("MemAvailable")}


def vram():
    """[{gpu, used_gb, total_gb}] for the 4 R9700 cards (amd-smi)."""
    rc, out = sh("amd-smi metric -m --json", timeout=30)
    try:
        d = json.loads(out)
        d = d if isinstance(d, list) else d.get("gpu_data", d)
        res = []
        for g in d:
            if g.get("gpu") in R9700:
                mu = g.get("mem_usage", {})
                res.append({"gpu": g["gpu"], "used_gb": mu["used_vram"]["value"] / 1024,
                            "total_gb": mu["total_vram"]["value"] / 1024})
        return res
    except Exception:
        return []


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1000:
            return f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} PB"
