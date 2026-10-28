---
name: download-llm
description: Use when the user wants an LLM (or its vision projector / draft head) downloaded to ~/models ("download qwen", "get the best 30B coding model") - picks repo and quant for 4x R9700, checks disk, downloads in the background. Next step /add-new-model-to-config. Input - model name or need.
---
# /download-llm
**Goal:** the right files of the right model in `~/models/<slug>/`. **Input:** a model name ("Qwen3.8-Flash-Next",
"gemma 4 26b") or a need ("best open coding model for one 32 GB GPU"). **Output:** finished download + report.
`S=~/Desktop/github_repos/local-rig-skills/skills/download-llm/scripts`

## Rules
1. Download only after the user agrees to the proposal (big downloads take disk and time).
2. Check `ls ~/models` first; do not download what is already there (also under another folder name).
3. Free disk by asking the user; delete with `gio trash` (never rm -rf on model folders).
4. Avoid quants below Q4 for agent/tool use.

## Steps
1. A description, not a name? Search current rankings with `web_search` (Open WebUI) / `rig-web_web_search`
   (llama.cpp UI) (e.g. "best open-weight coding model <month year>", Artificial Analysis, LMArena, the vendor
   blog), read 2-3 sources, name 1-3 concrete models with why.
2. `python3 $S/hf_find.py search "<name>" --gguf` (drop `--gguf` for vLLM safetensors).
3. `python3 $S/hf_find.py files <repo>` -> quants with total sizes and the include pattern for each.
4. Propose (table below) using "Choosing" and wait for the user's yes.
5. Check, then start (runs detached, survives the chat):
```bash
python3 $S/download.py plan  <repo> --include "*UD-Q5_K_XL*" --include "mmproj-F16.gguf"   # check only
python3 $S/download.py start <repo> --include "*UD-Q5_K_XL*" --include "mmproj-F16.gguf"   # starts in background
python3 $S/download.py status                                                               # progress, ETA
```
6. Verify: `status` says DONE, sizes match; GGUF: `ls -la <dest>`, all split files present (`-0000N-of-0000M`).
   Optional header check (no GPU, seconds):
   `python3 ~/Desktop/github_repos/local-rig-skills/bin/model_facts.py <first .gguf>`
7. Report (template below), then ask: "Should I run /add-new-model-to-config for this model now?" If yes, read that
   skill's SKILL.md and follow it with the downloaded path.

## Choosing
- Hardware: 4x Radeon AI PRO R9700, 32 GB VRAM each (GPU 0-3); RAM 60 GB is the tighter limit; /home ~0.8 TB free.
- Engine -> format: **llama.cpp** (ROCm or Vulkan) -> **GGUF**, default for anything new (MoE on one card: the
  Vulkan build is often faster). **vLLM** (Radiance fork for R9700, Docker) -> **safetensors** (FP8 or BF16), best for
  many parallel agents. **radiance** (StillDeadcode) -> **.rad** (Qwen3.8-Flash-Next only so far).
- Size: weights + KV cache + ~1 GB must fit the cards. <= 26 GB file -> 1 GPU with long context; <= 55 GB -> 2 GPUs;
  <= 110 GB -> 4 GPUs. Fewer GPUs = faster (less traffic between cards).
- GGUF quant: dense <= 30B -> Q8_0 (no measurable loss); bigger or MoE -> unsloth UD-Q5_K_XL or UD-Q4_K_XL.
  Uploaders: **unsloth** (UD dynamic quants, also mmproj + MTP files), **bartowski**, **ggml-org**,
  **lmstudio-community**. safetensors: the vendor's own repo (FP8 if published).
- Also fetch when they exist: `mmproj-*.gguf` (reads images; F16 for Vulkan) and an MTP/draft head (`mtp-*.gguf`,
  faster generation). Skip `imatrix`, other quants and `original/` folders.

## Reply
Proposal (step 4): `| repo | quant | size | GPUs | engine | extra files (mmproj/MTP) | time at ~50 MB/s |` + which
one you recommend and why.
Report (step 7):
```
Downloaded: <repo> <quant> -> <dest> (<size>)
Disk left: <GB>
Next: run /add-new-model-to-config now?
```

## Gotchas
- Destination is `~/models/<slug>/`; override with `--dest ~/models/<name>` (one folder per model family, quants
  in sub-folders if you keep several). vLLM repos: whole repo, no `--include`, into `~/models/<Vendor-Model-FP8>/`.
- `plan`/`start` refuse when less than 100 GB / 10 % of /home would stay free -> show `du -sh ~/models/* | sort -h`
  and ask what to delete (rule 3).
- Gated repo / HTTP 403: the user must accept the licence on the model page with the account **michal-konik**.
- A STOPPED download resumes with the same `start` command.

## Before you finish
- [ ] The user agreed before `start`.
- [ ] `status` says DONE and all files are present.
- [ ] You asked about /add-new-model-to-config.
