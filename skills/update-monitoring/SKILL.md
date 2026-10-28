---
name: update-monitoring
description: Use when the rig's Netdata monitoring or e-mail alerts must change ("hotspot alert at 95", "alert when RAM < 6 GB", "send alerts to X", new chart) - rules, AMD GPU collector, recipients, netdata.conf; staged, checked, one approved sudo command, undo. Input - the change.
---
# /update-monitoring
**Goal:** the monitoring change live, verified, with an undo. **Input:** what should change ("hotspot alert at 95
instead of 90", "alert when RAM available < 6 GB", "send alerts also to X", "add a chart for llama-swap's loaded
model"). **Output:** change applied + docs + report. `S=~/Desktop/github_repos/local-rig-skills/skills/update-monitoring/scripts`

## Rules
1. Show the design and its behaviour (when it fires, how many mails) and get the user's yes before staging.
2. Edit the staged copy only; apply with exactly the ONE command `stage.py apply-cmd` prints, through the sudo
   approval tool with a clear reason. One root command per approval; no chmod/chown of other files.
3. `/etc/msmtprc` and `~/.secrets/` hold an app password: never print, cat or copy them. Touch `/etc/msmtprc` only
   if the user asked to change SMTP (then follow their instructions and keep mode 0640 root:netdata).
4. Prefer `template:` on a context over per-chart `alarm:`; never write per-card copies of a rule.

## Steps
1. State: `python3 $S/netdata_state.py` (summary, alarms not CLEAR, rule names), `... alarm <name>` (thresholds,
   source line), `... charts <filter>` / `... chart <id>` (what data exists), `... files` (owners, hashes).
2. Design in plain words + the exact new/changed rule lines. Every rule needs `on`, `lookup` or `calc`,
   `warn`/`crit`, `every` (when no lookup), `to: sysadmin`, `info`; use `delay:` against flapping, `repeat:`
   sensibly. New metric: check a chart provides it; if not, extend the collector (add a chart definition in the
   CHART section of amdgpu.plugin and its values in the update loop, following the existing code) and restart
   netdata. Get the user's yes (rule 1).
3. Stage: `python3 $S/stage.py new <TARGET>`. Root-only files: request approval for `cat <TARGET>` (reason: "read
   current rules to edit a copy"), save the output with write_file, then `stage.py new <TARGET> --from <that file>`
   (or use the staged public copy after verifying `sha256sum` as the script explains).
4. Check: `python3 $S/stage.py check <STAGED> <TARGET>` and `stage.py diff <STAGED> <the copy you started from>`.
5. Apply: `python3 $S/stage.py apply-cmd <STAGED> <TARGET>` prints ONE command (install with backup + reload) and its
   undo; run it via the sudo approval tool (rule 2).
6. Verify: `netdata_state.py alarm <name>` shows the new thresholds/status and source; collector changes:
   `netdata_state.py charts amdgpu` shows the new chart and `systemctl status netdata` is active (if not, ask
   approval for `journalctl -u netdata -n 50`). Test mails only if the user wants them: approval for
   `sudo -u netdata /usr/lib/netdata/plugins.d/alarm-notify.sh sysadmin test` (3 mails).
   Anything wrong -> run the printed undo via approval.
7. Record (stage.py already wrote the journal line):
   `python3 ~/Desktop/github_repos/llm-private-education/tools/snapshot-configs.py` (root-only files: hash only),
   update `en/06-MONITORING.md` + `pl/06-MONITORING.md` (what, when, why), commit and push. Generic and useful to
   others (rules, collector)? Ask first, then update the public `radeon-r9700-rocm-notes/monitoring/` copy in a
   separate commit.
8. Reply: what changed, verification result, the undo command, docs updated.

## How it works here (facts - do not re-discover)
- **Netdata 1.43.2** (apt, systemd `netdata`), GUI http://192.168.0.39:19999 (LAN, no login), API
  http://127.0.0.1:19999/api/v1. No Netdata Cloud, no go.d plugin.
- **GPU collector** `/usr/lib/netdata/plugins.d/amdgpu.plugin` (Python, root:root 0755), because the built-in drm
  collector misses cards in runtime-suspend (`[plugin:proc] /sys/class/drm = no`). Runs `amd-smi` every 5 s, 13
  charts per card: `amdgpu_gpu0..3` = the R9700s (amd-smi/HIP numbers), `amdgpu_gpu4` = iGPU (ignore), plus
  `amdgpu_host` (CPU/NVMe/NIC temps; NVMe SMART from `/run/amdgpu-plugin-smart.json`, written every 15 min by root
  timer `smart-helper.timer` -> `/usr/local/sbin/smart-helper`). Enabled in `/etc/netdata/netdata.conf`
  `[plugins] amdgpu = yes` (`rig = no`; the `*.orphaned-2026-09-28` files are an old unused version - ignore).
- **Our rules** `/etc/netdata/health.d/amdgpu.conf` (root:netdata 0640): `template:` rules on `amdgpu.*` contexts
  (cover every card): hotspot, memory and edge temperature, cooling_fault (fan 0 RPM while hot), ECC, PCIe AER, PCIe
  width degraded, host CPU/NVMe/NIC temps, NVMe critical_warning/media_errors/wear; all `to: sysadmin`. Stock rules
  (RAM, disk, load, network...) in `/usr/lib/netdata/conf.d/health.d/`; override one by copying it into
  `/etc/netdata/health.d/`.
- **E-mail**: alarm -> `/usr/lib/netdata/plugins.d/alarm-notify.sh` (this package's health_alarm_notify.sh) reading
  `/etc/netdata/health_alarm_notify.conf` (`SEND_EMAIL="YES"`, `DEFAULT_RECIPIENT_EMAIL`, `EMAIL_SENDER`,
  `role_recipients_email[sysadmin]`) -> `sendmail` = msmtp -> `/etc/msmtprc` (Gmail SMTP, sender
  offlinelocalagents@gmail.com) -> michal.konik.praca@gmail.com. Log `/var/log/msmtp/msmtp.log`.
- Public copy (generic, no secrets): `~/Desktop/github_repos/radeon-r9700-rocm-notes/monitoring/`.

## Gotchas
- Known wart: `amdgpu_hotspot_high` has no `delay:`, so wavy load sends bursts of mails; fix: `delay: up 1m down 5m`.
- Syntax: https://learn.netdata.cloud/docs/alerts-&-notifications/health-configuration-reference - newer docs may
  describe options 1.43 lacks.

## Before you finish
- [ ] The user approved the design; exactly one root command per approval.
- [ ] Verified with `netdata_state.py`; undo command given; docs updated.
