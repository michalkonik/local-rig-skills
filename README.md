# local-rig-skills

Skills for the local AI models on my rig (mkoniu-B850-AI-TOP, 4x Radeon AI PRO R9700). A skill is a folder with a
`SKILL.md` (when to use it + a step-by-step procedure) and optional scripts. Every model served by llama-swap can use
them, in both chat UIs, and so does the OpenClaw agent Pedro. *Polska wersja: [README_PL.md](README_PL.md).*

**Rig and models**

| Skill | What it does |
|---|---|
| `/download-llm <model or need>` | finds the right repo and quant on Hugging Face, checks disk space, downloads in the background, then offers `/add-new-model-to-config` |
| `/add-new-model-to-config <model> [engine/config] [role]` | adds the model to llama-swap (llama.cpp ROCm/Vulkan, vLLM, radiance), tests it and tunes it for speed without losing quality |
| `/inspect-current-config-of-model <model>` | audits a model's setup, researches online for better settings or files, proposes changes and applies the approved ones via `/update-config-of-model` |
| `/update-config-of-model <model> <changes>` | applies config changes one at a time: backup, smoke test, benchmark before/after, rollback what does not help |
| `/update-monitoring <change>` | changes Netdata alerts, the GPU collector or e-mail alerting with staged files, one approved sudo command, and an undo |
| `/update-openclaw-config <change>` | changes OpenClaw (Pedro): models, sub-agents, plugins, skills, agents, channels, approvals, tools, MCP or a custom capability - finds the exact config path, backs up, dry-runs a JSON5 patch, tests with a real agent turn, keeps an undo |
| `/apply-change-on-local-machine <change>` | any other change to the machine: plan, destructive-command check, backup, apply, verify, journal |
| `/load-rig-context` | gives a fresh agent the map of the rig (paths, services, models, tools, rules, which doc to read) plus a live-state script; short, meant to be loaded often |

**Research and reading**

| Skill | What it does |
|---|---|
| `/find-in-internet <question>` | web research with cited sources |
| `/find-in-dark-web <query>` | onion search through the local Tor proxy (legitimate research only) |
| `/transcript-youtube-video <URL or name>` | full transcript of a YouTube video as .md with timestamps - captions first, local Whisper (Speaches) when there are none |
| `/select-meaningful-information-from-text <text or file>` | the key points of a long text or transcript: TL;DR, ranked points with evidence and timestamps, takeaways, claims to verify, skip/skim map |

**Content: X and YouTube (workspace `~/content/`)**

| Skill | What it does |
|---|---|
| `/content-voice` | builds your voice profile from your own writing (measured numbers + quoted examples); drafts are checked against it |
| `/content-ideas` | ideas from your rig's real activity + niche trends (HF trending, r/LocalLLaMA, HN, llama.cpp releases), scored, each with the command that proves it |
| `/write-x-post <idea or URL>` | one English X draft from a content idea, in your voice, with real numbers; you post it by hand. Not the two-account day loop |
| `/x-operate` | two X accounts: morning brief, audit, who to talk to, follow or unfollow, and drafts. You post by hand |
| `/x-voice` | rewrite a draft so it sounds like you: English on @local_agents, Polish on @youroldpalhorse |
| `/make-youtube-video <idea>` | real terminal captures -> narrated slides, charts, code (local Kokoro TTS), captions, chapters, thumbnail A/B, titles - all on the rig |
| `/make-youtube-short <finding>` | 30-55 s vertical video with burned captions from one real result |
| `/publish-youtube-video <slug>` | upload via the YouTube Data API as private/scheduled with thumbnail, captions, AI-disclosure flag |
| `/content-weekly-review` | your X and YouTube analytics exports -> what worked, one experiment, next week's plan |

**Income (search and triage; the final act stays yours)**

| Skill | What it does |
|---|---|
| `/claim-money-owed` | EU261 flight compensation and other claims: amount, deadline, ready letter (EN/PL) you send |
| `/track-bank-promotions` | Polish bank promotions: new/ended, conditions checklist with dates |
| `/find-freelance-gigs` | public freelance listings scored against your profile, proposal drafts you submit by hand |
| `/scan-bailiff-auctions` | official bailiff e-auctions: discount vs appraisal, deposit and dates, a shortlist you decide on |
| `/income-ledger` | the shared income ledger (SQLite): attempts, hours, costs, revenue, kill-check |
| `/income-weekly-review` | weekly page from the ledger: numbers per stream, keep/kill verdicts per the course's criteria, upcoming deadlines, your decisions |
| `/deal-hunter <status, deals, show, explain, books, start, stop>` | query and control the Deal Hunter agent (undervalued-hardware deals, tiers, net breakdown, costs); it only finds deals, never buys or contacts sellers |

**Notes (Joplin). OneNote is retired; the OneNote skills are removed.**

| Skill | What it does |
|---|---|
| `/joplin-list` | notebook tree, or the notes in one notebook |
| `/joplin-read` | search notes and print one note as text |
| `/joplin-write` | create a notebook or note, or append text; sends only with `--apply` |
| `/joplin-actions` | action to-dos sorted by deadline; sends only with `--apply` |

The script is `bin/joplin.py`. Do not read or write OneNote.

**OneDrive (Graph token, scope `Files.ReadWrite`)**

| Skill | What it does |
|---|---|
| `/drive-list` | list one folder or search the drive |
| `/drive-read` | print a small text file, or the size when it is not text |
| `/drive-write` | upload, create a folder, or delete one item; sends only with `--apply` |

Script: `bin/drive.py`. Token: Bitwarden item `onenote`, field `access_token` (`bw-secret onenote#access_token`). The item name is only the token store. A token copied before consent cannot call the drive.

**Google Drive (account `michal.konik.praca@gmail.com`, OAuth scope `drive`)**

| Skill | What it does |
|---|---|
| `/gdrive-list` | list one My Drive folder, or search by name |
| `/gdrive-read` | preview a Doc or small text file, or download (Sheets as xlsx, Docs as docx) |
| `/gdrive-write` | upload, replace a Doc/Sheet, write cells, create a folder, or trash one item; sends only with `--apply` |

Script: `bin/gdrive.py`. Token: `~/Documents/keep/gmail-tokens.json`. Not the OneDrive script. Cell writes need the Sheets API enabled on the OAuth project.

**PKO (Enable Banking, read only)**

| Skill | What it does |
|---|---|
| `/pko-balance` | balances and the credit-card limit for the consented PKO accounts |
| `/pko-transactions` | transactions for an inclusive date range |
| `/pko-card-timeline` | days until card interest only when the bank feed includes a due date |

Script: `bin/pko.py`. Secrets: Bitwarden item `enablebanking-pko` (`bw-secret`, never in git). mBank stays on `/read-mbank-balance`. The control-panel account link activates the app; balances need one API consent session.

**Gate.io (read only)**

| Skill | What it does |
|---|---|
| `/gate-balance` | spot balances, available and locked, for the whitelisted key |
| `/gate-transactions` | spot ledger history, and personal trades when a pair is named |
| `/gate-withdrawals` | withdrawal and deposit history; it does not send a withdrawal |

Script: `bin/gate.py`. Secrets: Bitwarden item `gateio`, fields `key` and `secret` (`bw-secret`, never in git). No orders or transfers.

**Budget sheet**

| Skill | What it does |
|---|---|
| `/manage-budget-file` | fills Google Sheet `Budżet 2026` from mBank and PKO, one tab per month, ten categories with date, amount, and description; yellow B1 is the editable monthly budget; Log tab says how far the bank read got |

Script: `bin/budget.py`. The sheet id is in `~/.local/state/rig-skills/budget.json`, not in git.
Full generated list: [INDEX.md](INDEX.md).

## How the models get the skills
- **Open WebUI** (`https://192.168.0.39:3443` or `http://192.168.0.39:3000`): every skill is registered as a native
  Open WebUI Skill. Models with native tool calling see the list and load a skill with their `view_skill` tool when
  it fits. To pick one yourself, type `/` in the chat box: every skill is in the menu with autocomplete
  (`/dow` -> `/download-llm`); choose it and type your request after it. `$` lists the skills as well.
- **llama.cpp chat UI** (llama-swap, `http://192.168.0.39:8080`): the catalog is part of each model's system prompt
  (written by `~/.config/llama-swap/tools/sync_prompts.py`); a message starting with `/skill-name` makes the model
  read that `SKILL.md` with its file tool and follow it.
- **OpenClaw (Pedro)** loads this `skills/` folder directly (`skills.load.extraDirs`, since 29 Oct 2026).
- **Scripts** run on the rig through the models' shell tools. Root actions always go through the sudo approval
  page (you approve each command with your password; the models never see it).

## Layout
```
skills/<name>/SKILL.md        instructions (front matter: name, description); <name>/scripts/ skill-only scripts
bin/                          shared tools: ls_entry.py (safe llama-swap edits), model_facts.py (GGUF/safetensors
                              facts + GPU plan), smoke.py (load/answer/tool/vision test), bench.py (speed before/after),
                              model_report.py (one-page model audit), bg (background jobs), sync_skills.py (publish)
lib/                          rig.py (paths, llama-swap, resources, backups, journal), hf.py (Hugging Face API),
                              content.py (content workspace, X length, AI-tell lint), ledger.py (income ledger), income.py (polite fetching, NBP rates)
reference/skill-format.md     the house format for skills on local models (read before writing one)
reference/rig-map.md          full rig tables behind /load-rig-context
reference/serving-playbook.md rules learned on this rig for engines, flags, limits and measuring
reference/openclaw-config.md  OpenClaw config paths, recipes, custom capabilities, docs map (/update-openclaw-config)
```
State written by the scripts (not in git): `~/.local/state/rig-skills/` - `journal.log` (every change with its undo),
`backups/`, `bench/`, `downloads/`, `jobs/`, `monitoring/`.

## Add or change a skill
1. Create `skills/<name>/SKILL.md` from the template in `reference/skill-format.md`: work in a script, body under
   6k characters (hard cap 10k), description under 300 characters starting "Use when...". Test it once through
   Pedro or Open WebUI with a real request.
2. `python3 bin/sync_skills.py` - validates, regenerates INDEX.md, updates Open WebUI and all system prompts.
3. Commit and push.

Docs of the whole setup (private): `~/Desktop/github_repos/llm-private-education` (chapter 05 = skills).
