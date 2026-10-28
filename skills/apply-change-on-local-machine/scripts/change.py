#!/usr/bin/env python3
"""Guard rails for /apply-change-on-local-machine: refuse destructive commands, back files up, keep a journal.

  change.py check "<command>"          exit 3 + reason if the command matches a destructive pattern, else OK
  change.py backup FILE [FILE ...]     copy files to ~/.local/state/rig-skills/backups/<time>/ (prints the paths)
  change.py log "<what changed, why, how to undo>"     one line in ~/.local/state/rig-skills/journal.log
  change.py history [N]                last N journal lines (default 20)

The agent applies the change with its own tools (shell, write/edit file, sudo approval tool); this script only
checks, backs up and records. Nothing here runs the change itself.
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import rig

DANGEROUS = [
    (r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(/|~|\$HOME|/home|/etc|/usr|/var|/boot)(\s|/?$|/\*)", "recursive delete of a system or home root"),
    (r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\b", "recursive rm - use `gio trash PATH` instead (recoverable)"),
    (r"\bdd\b.*\bof=/dev/", "raw write to a device"),
    (r">\s*/dev/(sd|nvme|vd)", "redirect into a disk device"),
    (r"\bmkfs(\.\w+)?\b", "formats a filesystem"),
    (r"\b(fdisk|parted|sgdisk|wipefs)\b", "partitioning"),
    (r"(curl|wget)[^|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "pipes a download into a shell"),
    (r"\bchmod\s+(-R\s+)?777\s+/", "world-writable system path"),
    (r"\bchown\s+-R\s+\S+\s+/(\s|$)", "recursive chown of /"),
    (r":\(\)\s*\{\s*:\|:&\s*\};:", "fork bomb"),
    (r"\b(shutdown|poweroff|reboot|halt)\b", "power action - ask the user to do it"),
    (r"\bsystemctl\s+(stop|disable|mask)\s+(llama-swap|netdata|docker|ssh|rig-tools)\b", "stops a core service of this rig"),
    (r"(/etc/msmtprc|\.secrets/|rig-tools/token|\.rig-agent-token|huggingface/token)", "touches a secret"),
    (r"\bgit\s+push\s+.*--force", "force push"),
]


def check(cmd):
    for pat, why in DANGEROUS:
        if re.search(pat, cmd):
            print(f"REFUSED: {why}  (pattern {pat})\nIf the user really wants this, explain the risk and let them "
                  "run it themselves, or find a safer equivalent.")
            return 3
    print("OK: no destructive pattern found (still: back up files you change, prefer reversible steps)")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "check":
        sys.exit(check(" ".join(a[1:])))
    elif a[0] == "backup":
        for f in a[1:]:
            print(f"{f} -> {rig.backup(f)}")
    elif a[0] == "log":
        print(rig.journal("apply-change", " ".join(a[1:])))
    elif a[0] == "history":
        n = int(a[1]) if len(a) > 1 else 20
        print("".join(rig.JOURNAL.read_text().splitlines(True)[-n:]) if rig.JOURNAL.is_file() else "journal is empty")
    else:
        sys.exit(__doc__)
