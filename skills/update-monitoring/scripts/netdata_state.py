#!/usr/bin/env python3
"""Read-only view of this rig's Netdata monitoring (no sudo needed).

  netdata_state.py                    summary: version, plugins, chart families, alarms not CLEAR, rule sources
  netdata_state.py alarm NAME         every instance of one alarm/template: status, value, thresholds, source file:line
  netdata_state.py charts [FILTER]    chart ids (e.g. "amdgpu_gpu1", "sensors", "mem")
  netdata_state.py chart ID           dimensions and the last values of one chart
  netdata_state.py files              the config files that matter, owner/mode, sha256 (where readable)

Netdata API: http://127.0.0.1:19999 (GUI http://192.168.0.39:19999, LAN, no login).
"""
import collections, grp, hashlib, html, json, os, pwd, sys, urllib.request

API = "http://127.0.0.1:19999/api/v1"
FILES = [
    "/etc/netdata/netdata.conf",                         # [plugins] amdgpu = yes; web bind; /sys/class/drm = no
    "/etc/netdata/health.d/amdgpu.conf",                 # our alert rules (templates on amdgpu.* contexts)
    "/etc/netdata/health_alarm_notify.conf",             # e-mail: SEND_EMAIL, DEFAULT_RECIPIENT_EMAIL, sender
    "/usr/lib/netdata/plugins.d/amdgpu.plugin",          # our collector (Python, amd-smi + sensors + SMART file)
    "/usr/local/sbin/smart-helper",                      # root helper writing NVMe SMART to /run/amdgpu-plugin-smart.json
    "/etc/systemd/system/smart-helper.service",
    "/etc/systemd/system/smart-helper.timer",
    "/usr/local/bin/gpu-status",                         # one-page status command
    "/etc/msmtprc",                                      # SMTP (Gmail app password inside - NEVER print it)
]


def get(path):
    with urllib.request.urlopen(API + path, timeout=15) as r:
        return json.loads(r.read())


def summary():
    info = get("/info")
    print(f"netdata {info.get('version')}  (apt package; config /etc/netdata; plugins /usr/lib/netdata/plugins.d)")
    charts = get("/charts")["charts"]
    fam = collections.Counter(k.split(".")[0] for k in charts)
    gpu = sorted(f for f in fam if f.startswith("amdgpu"))
    print(f"charts: {len(charts)}; our collector families: {', '.join(f'{f}({fam[f]})' for f in gpu)}")
    print("  amdgpu_gpu0..3 = the four R9700 (same numbering as amd-smi/HIP), amdgpu_gpu4 = iGPU, amdgpu_host = CPU/NVMe/NIC")
    al = get("/alarms?all")["alarms"]
    by_src = collections.Counter(v.get("source", "?").split("@", 1)[-1] for v in al.values())
    print(f"alarms: {len(al)} instances; rule files: " + ", ".join(f"{s} ({n})" for s, n in by_src.most_common()))
    bad = [(k, v) for k, v in al.items() if v["status"] not in ("CLEAR", "UNDEFINED", "UNINITIALIZED")]
    print(f"not CLEAR now: {len(bad)}")
    for k, v in bad:
        print(f"  {v['status']:8} {k}  value {v.get('value')} {v.get('units', '')}  ({v.get('info', '')[:80]})")
    names = sorted({v["name"] for v in al.values() if v.get("source", "").endswith("amdgpu.conf")})
    print("our rules (health.d/amdgpu.conf): " + ", ".join(names))


def alarm(name):
    al = get("/alarms?all")["alarms"]
    hits = {k: v for k, v in al.items() if v["name"] == name or k == name}
    if not hits:
        sys.exit(f"no alarm {name}; list: netdata_state.py (summary)")
    for k, v in sorted(hits.items()):
        keep = {x: v.get(x) for x in ("status", "value", "units", "chart", "warn", "crit", "lookup_method",
                                      "lookup_after", "calc", "delay", "repeat", "recipient", "source", "info")}
        print(k, html.unescape(json.dumps({x: y for x, y in keep.items() if y not in (None, "")}, indent=1)))


def charts(flt=""):
    for k in sorted(get("/charts")["charts"]):
        if flt in k:
            print(k)


def chart(cid):
    d = get(f"/data?chart={cid}&points=1&after=-10&format=json")
    print(cid, dict(zip(d["labels"], d["data"][0] if d["data"] else [])))


def files():
    for f in FILES:
        try:
            st = os.stat(f)
            owner = f"{pwd.getpwuid(st.st_uid).pw_name}:{grp.getgrgid(st.st_gid).gr_name} {oct(st.st_mode)[-4:]}"
        except FileNotFoundError:
            print(f"MISSING  {f}")
            continue
        try:
            h = hashlib.sha256(open(f, "rb").read()).hexdigest()[:16] if "msmtprc" not in f else "(secret - not read)"
        except PermissionError:
            h = "(root only - read via sudo approval)"
        print(f"{owner:24} {h:40} {f}")
    print("public copy of the collector + rules: ~/Desktop/github_repos/radeon-r9700-rocm-notes/monitoring/")


if __name__ == "__main__":
    a = sys.argv[1:]
    {"alarm": lambda: alarm(a[1]), "charts": lambda: charts(a[1] if len(a) > 1 else ""),
     "chart": lambda: chart(a[1]), "files": files}.get(a[0] if a else "", summary)()
