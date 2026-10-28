---
name: apply-change-on-local-machine
description: Use when the user wants something changed on this machine (install a package, edit a config, add a service, change a setting) - plan, check commands, back up, apply, verify, journal an undo. Not for models (/update-config-of-model) or Netdata (/update-monitoring). Input - the change.
---
# /apply-change-on-local-machine
**Goal:** the change made, verified and journalled with an exact undo. **Input:** what to change, in the user's
words. **Output:** the change applied + a short report.
`C=~/Desktop/github_repos/local-rig-skills/skills/apply-change-on-local-machine/scripts/change.py`
Model configs: /add-new-model-to-config or /update-config-of-model. Netdata: /update-monitoring.

## Rules
1. Run every command through `python3 $C check "<command>"` first. REFUSED (exit 3) means do not run it:
   explain why and offer a safer way.
2. Root only through the sudo approval tool (`request_sudo` in Open WebUI, `rig-web_request_sudo` in the llama.cpp
   UI): ONE clear command per approval, with a reason. Denied means stop. Never store or ask for the password.
3. Delete with `gio trash PATH` (recoverable).
4. Keep the firewall, SSH, llama-swap, netdata and rig-tools running; keep secrets (`/etc/msmtprc`, `~/.secrets/`,
   tokens) unprinted; keep GPU index 4 (iGPU) out of every GPU list; one big model load at a time (RAM 60 GB).

## Steps
1. Understand the current state with read-only commands (what is installed, which file controls it, is a service
   running). Find the real config file in `~/Desktop/github_repos/llm-private-education/en/08-CONFIG-MAP.md`.
2. Plan: numbered steps with exact commands/edits, which need root, how to verify, how to undo.
   If anything is irreversible, risky, or touches networking/boot/disks/drivers: show the plan and wait for the
   user's yes. Small, reversible, user-level changes may go ahead directly.
3. Check each command: `python3 $C check "<command>"` (rule 1).
4. Back up each file before editing: `python3 $C backup FILE...` (root-owned files:
   `cp FILE FILE.bak-$(date +%Y%m%d-%H%M)` next to it, inside the approved command).
5. Apply with your tools (rule 2). Long-running steps: `~/Desktop/github_repos/local-rig-skills/bin/bg NAME cmd...`.
6. Verify: service status, the setting read back, a functional test.
7. Journal: `python3 $C log "<what changed>; why; undo: <exact undo>"`. Earlier changes: `python3 $C history`.
8. If the change is part of the rig's setup (new service, port, config), tell the user it should be documented in
   llm-private-education (`tools/snapshot-configs.py` + the matching chapter, EN and PL) and offer to do it.

## Reply
```
Changed: <what>
Verified: <how, result>
Backup: <paths>
Undo: <exact command(s)>
Docs: <updated / offered / not needed>
```

## Before you finish
- [ ] Every command passed `check`; root commands went one per approval.
- [ ] The result was verified, and the journal line has the exact undo.
