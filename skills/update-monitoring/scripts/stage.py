#!/usr/bin/env python3
"""Stage, check and apply a Netdata config change with ONE approved sudo command (and an exact undo).

  stage.py new TARGET [--from FILE]   create ~/.local/state/rig-skills/monitoring/<time>/<name> to edit:
                                      a copy of FILE (e.g. the output of an approved `cat TARGET` saved to a file),
                                      or of the public repo copy when its sha256 matches what you were told.
  stage.py check STAGED TARGET        validate: health rules syntax / plugin compiles and emits charts / conf parses
  stage.py diff  STAGED TARGET|FILE   unified diff against the live file (if readable) or a given copy
  stage.py apply-cmd STAGED TARGET    print the single command to run through the sudo approval tool, and the undo

TARGET is one of the managed files:
  /etc/netdata/health.d/amdgpu.conf          root:netdata 0640, applied with `netdatacli reload-health`
  /etc/netdata/health_alarm_notify.conf      root:netdata 0640, read on every notification (no reload)
  /etc/netdata/netdata.conf                  root:root 0644,   needs `systemctl restart netdata`
  /usr/lib/netdata/plugins.d/amdgpu.plugin   root:root 0755,   needs `systemctl restart netdata`
  /etc/netdata/health.d/<new>.conf           root:netdata 0640, new rule file, `netdatacli reload-health`
"""
import difflib, os, pathlib, re, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import rig

STAGE = rig.STATE / "monitoring"
PUBLIC = pathlib.Path.home() / "Desktop/github_repos/radeon-r9700-rocm-notes/monitoring"
RULES = {
    "health.d": ("root", "netdata", "0640", "netdatacli reload-health"),
    "health_alarm_notify.conf": ("root", "netdata", "0640", None),
    "netdata.conf": ("root", "root", "0644", "systemctl restart netdata"),
    "plugins.d": ("root", "root", "0755", "systemctl restart netdata"),
}
HEALTH_KEYS = {"alarm", "template", "on", "class", "type", "component", "os", "hosts", "plugin", "module",
               "charts", "families", "chart labels", "host labels", "lookup", "calc", "every", "green", "red", "warn",
               "crit", "to", "exec", "delay", "repeat", "options", "info", "summary", "units", "label", "host_labels"}


def rule(target):
    for k, v in RULES.items():
        if k in target:
            return v
    sys.exit(f"{target} is not a managed Netdata file (see stage.py --help)")


def new(target, src=None):
    d = STAGE / rig.now()
    d.mkdir(parents=True, exist_ok=True)
    dst = d / pathlib.Path(target).name
    if src:
        shutil.copy2(os.path.expanduser(src), dst)
    elif os.access(target, os.R_OK):
        shutil.copy2(target, dst)
    else:
        pub = {"amdgpu.conf": PUBLIC / "health.d-amdgpu.conf", "amdgpu.plugin": PUBLIC / "amdgpu.plugin"}.get(dst.name)
        if pub and pub.is_file():
            shutil.copy2(pub, dst)
            print(f"live file is root-only; staged the public copy {pub}.\nVERIFY it equals the live file before "
                  f"editing: ask for approval of `sha256sum {target}` and compare with: {rig.sh(f'sha256sum {pub}')[1].split()[0]}")
        elif not os.path.exists(target):
            dst.write_text("")
            print("new file (target does not exist yet)")
        else:
            sys.exit(f"cannot read {target}: get its content with an approved `cat {target}`, save it to a file and use --from")
    print(f"staged: {dst}\nedit it, then: stage.py check {dst} {target}")


def check(staged, target):
    p = pathlib.Path(staged)
    txt = p.read_text()
    if "health.d" in target:
        errs, block = [], None
        for n, line in enumerate(txt.splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "\t" in line:
                errs.append(f"{n}: tab character")
            m = re.match(r"^\s*([a-z_ ]+?)\s*:\s*(.*)$", line)
            if not m:
                errs.append(f"{n}: not 'key: value': {s[:60]}")
                continue
            k, v = m.group(1), m.group(2)
            if k not in HEALTH_KEYS:
                errs.append(f"{n}: unknown key '{k}'")
            if k in ("alarm", "template"):
                if block:
                    errs += check_block(block)
                block = {"_line": n, k: v}
            elif block is None:
                errs.append(f"{n}: '{k}' before any alarm:/template:")
            else:
                block[k] = v
        if block:
            errs += check_block(block)
        print("\n".join(errs) if errs else f"OK health rules: {txt.count('template:') + txt.count('alarm:')} definitions")
        return not errs
    if "plugins.d" in target:
        r = subprocess.run([sys.executable, "-m", "py_compile", staged], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr)
            return False
        r = subprocess.run(["timeout", "15", sys.executable, staged, "2"], capture_output=True, text=True)
        out = r.stdout
        print(f"compiles; test run (15 s, as {os.environ.get('USER')}): {out.count('CHART ')} CHART, "
              f"{out.count('BEGIN ')} BEGIN lines; stderr: {r.stderr.strip()[-300:] or '-'}")
        return out.count("CHART ") > 0
    if target.endswith(".conf"):
        bad = [f"{n}: {l[:60]}" for n, l in enumerate(txt.splitlines(), 1)
               if l.strip() and not l.lstrip().startswith(("#", "[")) and "=" not in l]
        print("\n".join(bad) if bad else "OK conf syntax")
        return not bad
    return True


def check_block(b):
    e = []
    name = b.get("alarm") or b.get("template")
    if "on" not in b:
        e.append(f"{b['_line']}: {name}: missing 'on:' (chart or context)")
    if "lookup" not in b and "calc" not in b:
        e.append(f"{b['_line']}: {name}: needs 'lookup:' or 'calc:'")
    if "lookup" not in b and "every" not in b and "calc" in b:
        e.append(f"{b['_line']}: {name}: calc without lookup needs 'every:'")
    if "warn" not in b and "crit" not in b:
        e.append(f"{b['_line']}: {name}: no warn:/crit: - it can never fire")
    if "to" not in b:
        e.append(f"{b['_line']}: {name}: no 'to:' - set 'to: sysadmin' to get e-mails")
    return e


def diff(staged, other):
    try:
        a = open(other).read().splitlines(True)
    except PermissionError:
        sys.exit(f"{other} is root-only: diff against the copy you staged from instead")
    print("".join(difflib.unified_diff(a, open(staged).read().splitlines(True), other, staged)) or "(identical)")


def apply_cmd(staged, target):
    if not check(staged, target):
        sys.exit("fix the check errors first")
    owner, group, mode, after = rule(target)
    ts = rig.now()
    cmd = f"install -b -S .bak-{ts} -o {owner} -g {group} -m {mode} {staged} {target}"
    if after:
        cmd += f" && {after}"
    undo = (f"cp -a {target}.bak-{ts} {target}" + (f" && {after}" if after else "")
            if os.path.exists(target) else f"rm {target}" + (f" && {after}" if after else ""))
    print(f"ONE command for the sudo approval tool (reason: what changes and why):\n  {cmd}\n\nundo (also via approval):\n  {undo}")
    rig.journal("update-monitoring", f"prepared {target} from {staged}; apply: {cmd}; undo: {undo}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    if a[0] == "new":
        new(a[1], a[a.index("--from") + 1] if "--from" in a else None)
    elif a[0] == "check":
        sys.exit(0 if check(a[1], a[2]) else 1)
    elif a[0] == "diff":
        diff(a[1], a[2])
    elif a[0] == "apply-cmd":
        apply_cmd(a[1], a[2])
    else:
        sys.exit(__doc__)
