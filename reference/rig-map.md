# Rig map - details (companion to /load-rig-context)

`/load-rig-context` holds the paths, ports and rules every agent needs. This file holds the details: read it when you
need an exact doc file name, a tool version or login, the browser agent, an agent's details, Bitwarden, or the
rig-tools MCP tool list. State 30 Oct 2026. `R=~/Desktop/github_repos`.

## Machine
`mkoniu-B850-AI-TOP`, LAN 192.168.0.39, user `mkoniu`, Ubuntu 24.04.5, kernel 7.0, ROCm 7.2.4. Ryzen 7 9700X
(16 threads), 64 GB DDR5 = 60 GB usable. GPU 0-3 = 4x Radeon AI PRO R9700 (gfx1201, 32 GB each; amd-smi = HIP = PCI
order; GPU 0 drives the monitor). GPU 4 = iGPU (2 GB). `~/models` disk 1.8 TB.

## Repos and folders
| Path | What |
|---|---|
| `$R/llm-private-education` (private) | THE rig docs: `en/00-START-HERE.md` (one page), `en/08-CONFIG-MAP.md` (every config file + apply command + logs), `pl/` = Polish, `configs/` snapshots, `tools/snapshot-configs.py` |
| `$R/local-rig-skills` (private) | skills: `skills/*/SKILL.md`, `bin/` (bg, ls_entry.py, smoke.py, bench.py, model_report.py, model_facts.py, sync_skills.py), `lib/rig.py`, `reference/`; catalog `INDEX.md` |
| `$R/llm-education` (private, github.com/michalkonik) | courses on local LLMs/agents - generic, nothing rig- or person-specific |
| `$R/local-llm-perf-bench` (public), `local-llm-bench-results`, `local-llm-quality-bench` (private, github.com/michalkonik) | speed bench harness, published results, PL/EN quality bench |
| `$R/radeon-r9700-rocm-notes` (private, github.com/michalkonik) | RDNA4/ROCm notes, generic monitoring copy |
| `$R/local-browser-agent` (private, github.com/michalkonik/local-browser-agent) | browser agent for local models: `.venv/bin/python -m browser_agent run --url URL "task"` (`--headed`, `--mode test`); Playwright MCP 0.0.83 in `node_modules`; `config.toml` -> llama-swap, default model `uncensored`; secrets from Bitwarden folders `agents`/`agent-test`; `docs/` |
| `$R/family-finance-planner` (public, github.com/michalkonik) | personal app, unrelated to the rig |
| `$R/autonomous-crypto-agent` (private, github.com/michalkonik/autonomous-crypto-agent) | crypto agent: grows a portfolio measured in BTC, trades every allowlisted asset; paper only. Package/CLI `cryptoagent` (`.venv/bin/cryptoagent status`, `frozen verify`), `config/` (agent, models), `frozen/` (limits, allowlists, gate rules, lock; changed only by the user), `evolvable/` (the only files its self-improvement may write), `docs/` (OPERATIONS, SETUP, STRATEGY, TESTING); state `~/.local/state/cryptoagent`, data `~/.local/share/cryptoagent` |
| `$R/autonomous-deal-hunter` (local only, not on GitHub) | Deal Hunter: finds used electronics to resell; `dh` CLI in `.venv/bin`, `config/`, `docs/` (ARCHITECTURE, CONFIGURATION, OPERATIONS, ...), `var/` runtime data. No second checkout. |
| Not on github.com/michalkonik | `deal-hunter-log` and `finance-data` were deleted with the old account and were not recreated |
| `~/models` | all weights: `<model>/`, `comfyui/`, `speaches/`, `embed/` |
| `~/.config/llama-swap/` | `config.yaml` (models, aliases, groups; watched), `vllm/` + `radiance/` compose files, `tools/rig_tools.py`, `tools/sync_prompts.py`, `AGENT_BOOTSTRAP.md` |
| `~/.openclaw/` | `openclaw.json` (secrets), `workspace/` (Pedro's .md files), `patches/` |
| `~/.local/state/rig-skills/` | `journal.log` (every change + undo), `backups/`, `bench/`, `jobs/` |

## Services
| Port | Service (how it runs) |
|---|---|
| 8080 | llama-swap: OpenAI API `/v1`, `/running`, `/unload`, `/logs`, UI (systemd `llama-swap`) |
| 3000 / 3443 | Open WebUI http / https (mic needs https) (docker `open-webui`, `openwebui-https`) |
| 8765 on 172.17.0.1, 8766 | rig-tools MCP (systemd `rig-tools`): run_command, read/write/edit_file, list_directory, web_search, fetch_url, request_sudo + sudo_result; approval page :8766 |
| 8188 | ComfyUI (user svc `comfyui`; `comfyui-idle-free` restarts it after 5 idle min) |
| 8001 local | Speaches STT/TTS (docker `speaches`) |
| 18789 local | OpenClaw gateway (user svc `openclaw-gateway`) |
| 19999 / 9050 local / 8099 | Netdata / Tor SOCKS / rig-agent (remote shell for Claude on the Mac) |
| 8711 (LAN) | Deal Hunter web page, only while it runs (`dh start` starts the transient user unit `deal-hunter`) |
| none | crypto agent loop (user svc `cryptoagent`, enabled, 24/7, paper); LLM roles on qwen3.8-flash-next + qwen3.6-35b-a3b (group `duo`) |

## Tools on PATH
node 24.22, npm 11.19 (global prefix `~/.npm-global`), python 3.12 (venv per project), docker 29.1 + compose 2.40,
gh 2.102 (logged in as michalkonik), git as Koniu <michal.konik.job@gmail.com>, Bitwarden CLI
`~/.local/bin/bw` 2026.9.1 with `bw-agent-unlock` / `bw-agent-lock` / `bw-secret` / `openclaw-bw-resolver` (vault
folders `agents`, `agent-test`; session `~/.config/bw/session`), Bitwarden Secrets Manager CLI `bws` 2.1.0 (token
`~/.config/bws/agent-test.token`, set up by the user), Chrome 156 `/usr/bin/google-chrome`, npx. No uv.
OpenClaw CLI `~/.npm-global/bin/openclaw` (offline docs in `~/.npm-global/lib/node_modules/openclaw/docs/`).
Git: no AI attribution (Co-Authored-By, "Generated with") in michalkonik repos. Public repos, and private ones that stay generic, carry no rig
internals, secrets or personal data.

## Skills
The catalog is `$R/local-rig-skills/INDEX.md` (generated by `bin/sync_skills.py`: models, machine changes,
monitoring, OpenClaw, web search, YouTube/X, side income, Deal Hunter, Joplin, OneDrive).

## For X read Y (`$R/llm-private-education/en/`)
| Need | Read |
|---|---|
| hardware, BIOS, kernel, GPU tuning | `01-HARDWARE-AND-OS.md` |
| access, remote control, security | `02-HOW-TO-TALK-TO-THE-RIG.md` |
| models, llama-swap, engines, speeds | `03-MODELS-AND-SERVING.md`, `$R/local-rig-skills/reference/serving-playbook.md` |
| images, video, voice | `04-PICTURES-VIDEO-VOICE.md` |
| skills, Open WebUI integration | `05-SKILLS.md` |
| monitoring, alerts | `06-MONITORING.md` |
| repos, benchmarks, what is published | `07-REPOS-BENCHMARKS-PUBLISHING.md` |
| any config file, apply command, logs | `08-CONFIG-MAP.md` |
| why things are as they are / next ideas | `09-HISTORY.md` / `10-IDEAS-AND-NEXT-STEPS.md` |
| OpenClaw, Pedro | `11-OPENCLAW.md` (PL `pl/11-OPENCLAW.md`), `$R/local-rig-skills/reference/openclaw-config.md` |
| browser agent | `12-BROWSER-AGENT.md` (PL `pl/12-AGENT-PRZEGLADARKOWY.md`), `$R/local-browser-agent/README.md` + `docs/` |
| Deal Hunter | `13-DEAL-HUNTER.md`, `$R/autonomous-deal-hunter/README.md` + `docs/` |
| crypto agent | `$R/autonomous-crypto-agent/README.md` + `docs/` (no chapter in the rig docs yet) |
| private courses (EN + PL) | `../private-courses/` (contract to company, X/YouTube growth, AI second-order winners, biotech in the age of AI) |
| Joplin | Notes and action items. Skills `/joplin-list`, `/joplin-read`, `/joplin-write`, `/joplin-actions`. Script `bin/joplin.py`. OneNote is retired. |
| Gate.io | Read-only API v4. Skills `/gate-balance`, `/gate-transactions`, `/gate-withdrawals`. Script `bin/gate.py`. Bitwarden item `gateio`, fields `key` and `secret`. No orders and no withdrawals are sent. |
| OneDrive | Graph token in Bitwarden item `onenote`, field `access_token` (scope `Files.ReadWrite`). The item name is only the token store. Skills `/drive-list`, `/drive-read`, `/drive-write`. Do not print the token. |
