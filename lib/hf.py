"""Minimal Hugging Face Hub client (urllib only). Uses the token the `hf` CLI stored (~/.cache/huggingface/token)
or $HF_TOKEN, so gated repos the account (michal-konik) has accepted are visible. Never prints the token."""
import json, os, pathlib, re, urllib.parse, urllib.request

API = "https://huggingface.co/api"


def token():
    t = os.environ.get("HF_TOKEN")
    if t:
        return t.strip()
    p = pathlib.Path.home() / ".cache" / "huggingface" / "token"
    return p.read_text().strip() if p.is_file() else None


def get(path, params=None, timeout=30):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    headers = {"User-Agent": "rig-skills/1.0"}
    t = token()
    if t:
        headers["Authorization"] = "Bearer " + t
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return json.loads(r.read())


def search(query, limit=20, gguf=False):
    params = {"search": query, "limit": limit, "sort": "downloads", "direction": -1, "full": "true"}
    if gguf:
        params["filter"] = "gguf"
    return get("/models", params)


def info(repo):
    return get(f"/models/{repo}")


def tree(repo, revision="main"):
    """All files with sizes (LFS size when the file is in LFS)."""
    out = get(f"/models/{repo}/tree/{revision}", {"recursive": "true", "expand": "false"})
    files = []
    for f in out:
        if f.get("type") != "file":
            continue
        size = (f.get("lfs") or {}).get("size") or f.get("size") or 0
        files.append({"path": f["path"], "size": size})
    return files


QUANT_RE = re.compile(r"(?i)(UD-)?(IQ\d_[A-Z0-9_]+|Q\d_K(?:_[A-Z]+)?|Q\d_\d|Q\d_[A-Z0-9]+|BF16|F16|F32|MXFP4(?:_MOE)?|TQ\d_\d)")
SHARD_RE = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$")


def quant_of(path):
    name = path.rsplit("/", 1)[-1]
    m = QUANT_RE.search(name.replace(".gguf", ""))
    return (m.group(0).upper() if m else "?")


def classify(path):
    low = path.lower()
    if low.endswith(".gguf"):
        if "mmproj" in low:
            return "vision projector (mmproj)"
        if re.search(r"(^|[/_-])(mtp|nextn|draft|eagle|dflash|dspark)", low):
            return "draft / MTP head"
        return "gguf weights"
    if low.endswith(".safetensors"):
        return "safetensors weights"
    if low.endswith(".rad"):
        return "radiance .rad"
    return "other"
