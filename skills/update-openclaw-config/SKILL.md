---
name: update-openclaw-config
description: Use when anything in OpenClaw / Pedro must change (models, sub-agents, plugins, skills, agents, workspace, Telegram, exec approvals, tools, gateway, MCP, custom capabilities) - backup, JSON5 patch, dry-run, apply, test turn, undo. llama-swap entries: /update-config-of-model. Input - the change.
---
# /update-openclaw-config
**Goal:** the change applied, validated, proven with a real agent turn, with an undo. **Input:** the change in the
user's words ("sub-agents on qwen3.6-35b-a3b", "connect Telegram").
`O=~/Desktop/github_repos/local-rig-skills/skills/update-openclaw-config/scripts/oc.py`
Read `~/Desktop/github_repos/local-rig-skills/reference/openclaw-config.md` before planning: the section for your
area (1 paths, 2 recipes, 3 custom capabilities, 4 docs); 4a rig state + 4b full traps when the change touches
models, arrays, per-agent values or plugins.

## Rules
1. Wrap every OpenClaw CLI call in `timeout 60` (`doctor` can hang). CLI: `~/.npm-global/bin/openclaw`.
2. `~/.openclaw/openclaw.json` holds the gateway token and provider key: read it only via `python3 $O state`,
   `openclaw config get <path>` (redacted) and `python3 $O diff`. No secrets in patches.
3. Find every key in the schema/docs before writing it; change config with patch files, not wizards.
4. Wait for the user's yes when the change touches secrets, channels (opens Pedro to the outside), exec
   approvals/tool policy, gateway bind/auth/port, deletes anything, or loads a model that is not running. Small
   reversible changes (a limit, a description, enabling a bundled skill) may go ahead.
5. Back up with `oc.py backup` (OpenClaw's own `.bak` files rotate).

## Steps
1. State: `python3 $O state`; read what the change touches: `timeout 60 openclaw config get <path> --json`,
   workspace files (`~/.openclaw/workspace`).
2. Find the place: `python3 $O find '<word>'`, then `python3 $O schema <path>` (`agents.entries.<id>`,
   `...models[]`); `python3 $O docs '<words>'`, then read the section.
   Not in openclaw.json: exec approvals (`openclaw approvals ...`), workspace files, installed plugins/skills
   (`openclaw plugins|skills ...`). OpenClaw cannot do it -> cookbook section 3.
3. Plan: exact patch/commands, why, effect, restart or model load, test, undo (rule 4).
4. Back up: `python3 $O backup <what> [workspace files you will edit]` (prints the undo). Approvals change:
   `timeout 60 openclaw approvals get --json > ~/.local/state/rig-skills/openclaw/approvals-$(date +%Y%m%d-%H%M).json`.
5. Write `~/.openclaw/patches/<YYYYMMDD>-<what>.json5` (style: `20261028-pedro-models.json5`): a `//` comment with
   what and why, then only the changed keys. Objects merge, arrays and scalars replace, `null` deletes. Arrays
   (`models.providers.vllm.models`, `modelPolicy.allow`, `skills`, `allowFrom`, `bindings`...) are written complete,
   starting from `openclaw config get <path> --json`. Secrets: `tokenFile`, SecretRef
   `{ source: "env", provider: "default", id: "VAR" }` or the owning CLI (`openclaw channels add`).
6. Dry-run: `timeout 60 openclaw config patch --file <patch> --dry-run` -> `Dry run successful`.
   `Refusing to replace <path>; it would remove existing entries: ...` = your array lost entries: fix it, or if the
   removal is intended add `--replace-path <path>` (e.g. `--replace-path models.providers.vllm.models`).
   Schema errors name key and limit - check with `oc.py schema`.
7. Apply: same command without `--dry-run` (keep any `--replace-path`). Only if the last line says `Restart the
   gateway to apply.`: check `timeout 60 openclaw health` (restart ends running Pedro turns), then
   `systemctl --user restart openclaw-gateway`. Then
   `timeout 60 openclaw config validate` -> `Config valid`, and `python3 $O diff`: only the planned paths changed.
8. Test the behaviour: check `curl -s localhost:8080/running` and `free -g`, then
   `python3 $O test miclaw "<message that exercises the change>" [--model vllm/<id>]` (one turn in a NEW session).
   Pedro's primary is radiance (~30 GB):
   not loaded and < 35 GB RAM available -> ask first, or test a non-model change with
   `--model vllm/gemma-4-26b-a4b-pool`. If you run on a llama-swap model outside group `pedro`, loading Pedro's
   models unloads you: give the user the test command instead. Per-area checks: cookbook 4c.
   Wrong -> undo now (`cp -p <backup> ~/.openclaw/openclaw.json` or a reverse patch with old values / `null`),
   `openclaw config validate`, `oc.py diff <backup>` = identical; rethink.
9. Record: `python3 $O log "<what changed>; why; patch <file>; undo: cp -p <backup> ~/.openclaw/openclaw.json"`.
   Setup changes (models, agents, channels, plugins, MCP): update llm-private-education `en/03-MODELS-AND-SERVING.md`
   + `pl/03-MODELE-I-SERWOWANIE.md` OpenClaw section (+ `08-CONFIG-MAP` for new files/services), run its
   `tools/snapshot-configs.py`, commit and push.

## Reply
`Change: <what> | Patch: <file> | Backup: <file> | Test: <model, reply summary> | Undo: cp -p <backup> ~/.openclaw/openclaw.json`

## Gotchas
- Model ids are not checked until the first turn: check each against `curl -s localhost:8080/v1/models`; a model
  needs a `models.providers.vllm.models[]` entry and, for Pedro, a `agents.entries.miclaw.modelPolicy.allow` entry.
- `modelPolicy.allow` and `null` deletes change silently (unprotected); per-agent values replace defaults.
- Existing sessions keep their model and skills snapshot: always test in a new session.
- Orchestrator and sub-agent models share llama-swap group `pedro`, or every spawn swaps models.
- Only if asked: `openclaw configure`, `onboard`, `setup`, `doctor --fix`, `reset`. Exec approvals live in SQLite
  (`~/.openclaw/state/openclaw.sqlite`), outside config backups. Delete with `gio trash PATH`.

## Before you finish
- [ ] Dry-run passed, `Config valid`, `oc.py diff` shows only planned paths.
- [ ] A new-session test turn shows the change; the journal line has the undo.
