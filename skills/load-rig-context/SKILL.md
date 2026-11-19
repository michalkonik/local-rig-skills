---
name: load-rig-context
description: Use when you start work on this rig and need its map - limits, where repos, docs, configs and models live, ports, models, house rules, which doc to read - plus live state (RAM, GPUs, loaded models, ports). Input - none (optionally the task).
---
# /load-rig-context
1. Live state (~1 s): `python3 ~/Desktop/github_repos/local-rig-skills/skills/load-rig-context/scripts/rig_now.py`
2. Facts below are confirmed (30 Oct 2026); do not re-check them. If one is wrong, say so and fix this file.
3. Read `~/Desktop/github_repos/local-rig-skills/reference/rig-map.md` only when you need an exact doc file
   name, tool versions/logins, Bitwarden, the browser agent, an agent's details or the rig-tools MCP tool list.

## Rules
1. RAM (60 GB usable) is the limit, not VRAM. One radiance model (`qwen3.8-flash-next-uncensored`) at a time: it pins ~30 GB;
   a second radiance model beside it caused a kernel panic. Check `rig_now.py`/`free -g` first (GTT counts).
   Free all: `curl -s localhost:8080/unload`. GPU 4 (iGPU) never goes in a device list.
2. Never print, copy or commit secrets: `~/.secrets/`, `/etc/msmtprc`, `~/.config/rig-tools/token`,
   `~/.rig-agent-token`, `~/.cache/huggingface/token`, `HF_TOKEN` in `~/.bashrc`, `~/.openclaw/openclaw.json`,
   `~/.config/bw/`, bws token, any vault value.
3. Root only via `request_sudo` (one command + reason; user approves on :8766); never ask for the password.
   Delete with `gio trash PATH` (in /tmp: `rm -f FILE`). Third-party code (pip/npm, plugins, `curl | sh`,
   unknown models): the user's OK first.
4. Back up a config before editing, verify after, journal it with its undo.
5. Git: branch + PR, never push to main; no AI attribution in michalkonik repos; public repos stay generic.
6. Two autonomous agents share the GPUs (see Agents; `rig_now.py` prints whether they run). Deal Hunter uses group
   `pedro`, the crypto agent `duo`: loading a model outside the loaded group evicts the other agent's models. Never
   unload, stop, restart or reconfigure an agent unless the user asks. Never touch an agent's `frozen/` layer.

## Machine
`mkoniu-B850-AI-TOP` 192.168.0.39, user `mkoniu`, Ubuntu 24.04.5, ROCm 7.2.4. GPU 0-3 = 4x R9700 (gfx1201, 32 GB;
amd-smi = HIP order; GPU 0 drives the monitor), GPU 4 = 2 GB iGPU. `~/models` (1.8 TB) holds all weights.

## Paths (`R=~/Desktop/github_repos`)
- `$R/llm-private-education`: rig docs `en/`, `pl/`, `configs/`, `tools/snapshot-configs.py`, `private-courses/`
- `$R/local-rig-skills`: `skills/` (catalog `INDEX.md`), `bin/` (bg, ls_entry, smoke, bench, model_report,
  model_facts, sync_skills), `lib/rig.py`, `reference/`
- `$R/autonomous-crypto-agent` (private, GitHub) and `$R/autonomous-deal-hunter` (local only). No deal-hunter-dev checkout.
- Generic, no rig internals. Private: `$R/llm-education`, `$R/local-browser-agent`, `local-llm-quality-bench`,
  `local-llm-bench-results`, `radeon-r9700-rocm-notes`. Public: `$R/local-llm-perf-bench`, `$R/family-finance-planner` (other app).
- `~/.config/llama-swap/`: `config.yaml` (watched), `vllm/`, `radiance/`, `tools/sync_prompts.py`, `AGENT_BOOTSTRAP.md`
- `~/.openclaw/`: `openclaw.json` (secrets), `workspace/` (Pedro), `patches/`
- `~/.local/state/rig-skills/`: `journal.log`, `backups/`, `bench/`, `jobs/`

## Ports
8080 llama-swap (systemd; `/v1 /running /unload /logs`) | 3000/3443 Open WebUI (docker) | 8765 on 172.17.0.1
rig-tools MCP, 8766 sudo approval | 8188 ComfyUI | 8001 Speaches | 18789 OpenClaw | 9050 Tor | 19999 Netdata |
8099 rig-agent | 8711 Deal Hunter web page (only while it runs)

## Models (ttl 600 s)
`qwen3.8-flash-next-uncensored` (smartest; aliases: `qwen3.8-flash-next`, `qwen3.8`, `smartest` — censored Flash removed);
`qwen3.6-35b-a3b` / `-x4` (Huihui abliterated FP8); `gemma-4-26b-a4b`, `-pool` (4 slots); `bielik-11b` (Polish).
Flint removed (never cleared ≥100 t/s). Groups: `pedro` = flash-unc (GPUs 0+1) + gemma-pool (2+3);
`duo` = qwen3.6 only (llama-swap: one model, one group). Engines: radiance (flash-unc), vLLM fork (qwen3.6*),
llama.cpp ROCm `~/llama.cpp-e86f5fd`, Vulkan `~/llama.cpp-e86f5fd-vulkan` / `~/llama.cpp-0ce8cd1-vulkan`.
Status: `gpu-status`, `models-status`, `amd-smi metric -m`, `curl -s localhost:8080/logs`.
OpenClaw: agent `miclaw` = Pedro, always `timeout 60 openclaw ...`; changes via /update-openclaw-config.
Long jobs: `$R/local-rig-skills/bin/bg NAME cmd...`, poll `bg NAME`. Prefer the rig skills to improvising.
Avoid description-only `ls_entry` patches while models are loaded — reload unloads them.

## Agents (they propose and report; money decisions stay with the user)
- Crypto agent, `$R/autonomous-crypto-agent`: user svc `cryptoagent`, enabled, 24/7, **paper only (live stays disabled)**;
  grows a portfolio measured in BTC, trades every allowlisted asset. Status `.venv/bin/cryptoagent status`;
  docs `README.md`, `docs/OPERATIONS.md`. Limits, allowlists, policy engine and signer (`frozen/`) change only
  through the user.
- Deal Hunter, `$R/autonomous-deal-hunter`: started and stopped by hand (`dh start` / `dh status` / `dh stop`, venv
  `.venv/bin`; transient user unit `deal-hunter`, no autostart). Never buys or contacts sellers. Pedro queries it
  via /deal-hunter; doc `13-DEAL-HUNTER.md`.

## Notes and files
OneNote is retired. Do not read or write it.
Notes and action items: `/joplin-*`, script `bin/joplin.py`.
OneDrive token: `bw-secret onenote#access_token` (never print it). The item name is only the store. Scope `Files.ReadWrite`. Skills `/drive-*`, script `bin/drive.py`. Writes only with `--apply`.

## Docs (`$R/llm-private-education/en/`)
00 start | 01 hardware | 02 access | 03 models (+ `reference/serving-playbook.md`) | 04 media | 05 skills |
06 monitoring | 07 repos | 08 CONFIG-MAP (every config, apply command, logs) | 09 history | 10 ideas |
11 OpenClaw (+ `reference/openclaw-config.md`) | 12 browser agent | 13 Deal Hunter.
Private courses (EN + PL each): `../private-courses/`.
