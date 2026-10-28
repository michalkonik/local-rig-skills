#!/usr/bin/env python3
"""Live state of the rig in ~20 lines (read-only, no sudo, ~1 s): RAM, GPUs (VRAM/GTT/busy), loaded and available
models, llama-swap groups, OpenClaw models, the two agents, containers, service ports, disk, last journal lines.

  python3 ~/Desktop/github_repos/local-rig-skills/skills/load-rig-context/scripts/rig_now.py
"""
import json, pathlib, shutil, socket, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import rig

PORTS = {8080: "llama-swap", 3000: "open-webui", 3443: "webui-https", 8188: "comfyui", 8001: "speaches",
         8765: "rig-tools-mcp", 8766: "sudo-approval", 18789: "openclaw", 19999: "netdata", 9050: "tor", 8099: "rig-agent"}
HOSTS = {8765: "172.17.0.1"}
# user units of the autonomous agents; each holds a llama-swap group while it works
AGENTS = {"cryptoagent": "crypto agent (paper, duo)", "deal-hunter": "Deal Hunter (pedro, web :8711)"}


def gib(path):
    try:
        return int(pathlib.Path(path).read_text()) / 2**30
    except OSError:
        return None


def gpus():
    """The four R9700 in amd-smi/HIP order (PCI order); the 2 GB iGPU is skipped."""
    cards = []
    for dev in pathlib.Path("/sys/class/drm").glob("card[0-9]*/device"):
        tot = gib(dev / "mem_info_vram_total")
        if tot and tot > 8 and dev.parent.name.count("-") == 0:
            cards.append((dev.resolve().name, dev))
    out = []
    for i, (_, dev) in enumerate(sorted(cards)):
        busy = (dev / "gpu_busy_percent").read_text().strip() if (dev / "gpu_busy_percent").exists() else "?"
        out.append(f"{i}: {gib(dev / 'mem_info_vram_used'):.1f}/{gib(dev / 'mem_info_vram_total'):.0f}G "
                   f"gtt {gib(dev / 'mem_info_gtt_used'):.1f}G {busy}%")
    return out


def port_up(p):
    try:
        with socket.create_connection((HOSTS.get(p, "127.0.0.1"), p), timeout=0.3):
            return True
    except OSError:
        return False


def main():
    r = rig.ram_gb()
    load = pathlib.Path("/proc/loadavg").read_text().split()[:3]
    print(f"RAM {r['available']:.0f}/{r['total']:.0f} GB available (limit!)  load {' '.join(load)}")
    print("GPU " + " | ".join(gpus()) + "   (iGPU = 4, never use)")
    try:
        run = rig.http_json(rig.LS_URL + "/running", timeout=3).get("running", [])
        print("loaded: " + (", ".join(f"{m['model']} ({m.get('state')})" for m in run) or "none"))
        ids = sorted(m["id"] for m in rig.http_json(rig.LS_URL + "/v1/models", timeout=3)["data"])
        print("models: " + ", ".join(ids))
    except Exception as e:
        print(f"llama-swap :8080 not answering: {e}")
    try:
        print("groups: " + "; ".join(f"{g}={'+'.join(v.get('members', []))}" for g, v in rig.groups().items()))
    except Exception as e:
        print(f"groups: ? ({e})")
    try:
        d = json.loads((rig.HOME / ".openclaw/openclaw.json").read_text())["agents"]["defaults"]
        print(f"openclaw: primary {d.get('model', {}).get('primary')}, subagents {d.get('subagents', {}).get('model')}")
    except Exception as e:
        print(f"openclaw: ? ({e})")
    states = {u: rig.sh(f"systemctl --user is-active {u}", timeout=5)[1] or "?" for u in AGENTS}
    print("agents: " + ", ".join(f"{n} {states[u]}" for u, n in AGENTS.items()))
    rc, out = rig.sh("docker ps --format '{{.Names}}'", timeout=10)
    print("docker: " + (", ".join(out.split()) if rc == 0 else f"? ({out[:80]})"))
    up = [f"{p} {n}" for p, n in PORTS.items() if port_up(p)]
    down = [f"{p} {n}" for p, n in PORTS.items() if not port_up(p)]
    print("ports up: " + ", ".join(up))
    if down:
        print("ports DOWN: " + ", ".join(down))
    du = shutil.disk_usage(rig.MODELS)
    print(f"disk ~/models: {du.free / 1e9:.0f} GB free of {du.total / 1e9:.0f}")
    if rig.JOURNAL.is_file():
        for line in rig.JOURNAL.read_text().splitlines()[-2:]:
            print("journal: " + line[:150])
    warn = []
    if r["available"] < 10:
        warn.append(f"RAM {r['available']:.0f} GB available (< 10): unload before loading anything")
    if down:
        warn.append(f"{len(down)} port(s) down")
    print("WARN " + "; ".join(warn) if warn else "OK rig ready")


if __name__ == "__main__":
    main()
