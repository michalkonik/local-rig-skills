---
name: add-new-model-to-config
description: Use when a downloaded model should be served by llama-swap on this rig ("add this model", "serve it on GPU 3") - picks engine, GPUs, context, drafts, vision, sampling; tests, benchmarks, tunes, updates prompts and docs. Existing models: /update-config-of-model. Input - model, optional engine/role.
---
# /add-new-model-to-config
**Goal:** a working, measured llama-swap entry with the best tok/s at full quality. **Input:** the model (path under
~/models, a folder, or a name to find there), optional engine/config wishes ("vLLM", "on GPU 3", "2 slots", "long
context") and what it is for. **Output:** entry live, prompts and docs updated, report.
`B=~/Desktop/github_repos/local-rig-skills/bin`

## Rules
1. Read `~/Desktop/github_repos/local-rig-skills/reference/serving-playbook.md` once per task and follow it
   (limits, engine choice, flag checklist, optimisation order, failure causes).
2. Show the plan and get the user's confirmation before writing anything. If they gave a different config, follow
   theirs but warn about real problems.
3. Keep RAM >= ~10 GB available when loading (`free -g`); if another big model holds the cards you need:
   `curl -s localhost:8080/unload`. One heavy thing at a time.
4. A speed gain that lowers precision (smaller quant, KV q4, lossy draft acceptance) needs the user's yes after you
   explain the trade-off.
5. Long commands go through `$B/bg NAME cmd...`, polled with `$B/bg NAME` (tool calls time out after a few minutes).

## Steps
1. Current setup: `python3 $B/ls_entry.py list`; an entry to copy: `python3 $B/ls_entry.py show <similar id>`
   (Gemma = 1-card Vulkan llama.cpp, qwen3.8-flash-next-llamacpp = 4-card ROCm, qwen3.6-35b-a3b = vLLM,
   qwen3.8-flash-next = radiance).
2. Facts: `python3 $B/model_facts.py <path> [--ctx N]` (arch, size, native context, layers/heads, experts, MTP head,
   mmproj, cards per context size). Read the model card (`fetch_url https://huggingface.co/<repo>`): sampling,
   chat template / tool-calling notes, context limits, minimum llama.cpp/vLLM. Missing `mmproj` or MTP head from the
   uploader -> offer /download-llm.
3. Plan table (rule 2): engine + binary, GPUs (fewest that fit; GPU 0 drives the monitor, prefer 1-3 for one card),
   context and slots, KV type, ubatch (to be measured), draft/MTP, mmproj, sampling, ttl, id/aliases/name/
   description, group (default none = it unloads others; a group only if GPUs don't overlap and RAM fits),
   expected tok/s range by analogy with similar entries, what could go wrong.
4. Write `/tmp/<id>.entry.yaml`, indented like config.yaml (key line `  "<id>":`, fields at 4 spaces, `cmd: |` block
   at 6), starting with a comment block (indent 2): what it is, quant, sizes, why these flags.
5. `python3 $B/ls_entry.py add <id> /tmp/<id>.entry.yaml --dry-run` -> check the diff, then run it without
   `--dry-run`. Note the backup path it prints.
6. Smoke test (rule 3 first): `$B/bg smoke-<id> python3 $B/smoke.py <id> [--vision]`, then `$B/bg smoke-<id>` until
   FINISHED. On failure: `curl -s localhost:8080/logs | tail -80` and the playbook's "When a load fails".
7. Baseline: `$B/bg bench-<id> python3 $B/bench.py run <id> --label base`. Then ONE change at a time with
   `ls_entry.py patch <id> "old" "new"`, bench again with a new label, `bench.py compare`; keep a change only if it
   helps more than ~3 % (repeat if close). Order of candidates: playbook "Optimisation order". Stop when changes
   stop paying (usually 3-5 runs).
8. Write the final numbers into the entry's comment and `description` (`ls_entry.py patch`), then
   `python3 ~/.config/llama-swap/tools/sync_prompts.py` (prompts, llama.cpp UI file, Open WebUI model + vision flag).
9. Docs: `python3 ~/Desktop/github_repos/llm-private-education/tools/snapshot-configs.py`; add the model to the
   lineup in `llm-private-education` `en/03-MODELS-AND-SERVING.md` and `pl/03-MODELE-I-SERWOWANIE.md` (+ change log);
   `git -C ~/Desktop/github_repos/llm-private-education add -A && git commit -m "..." && git push`.
10. Reply with the template below.

## Reply
```
Entry: <id> (aliases ...) - pick it in Open WebUI / llama-swap UI
Speed: <tok/s gen>, <tok/s prompt>; VRAM <GB per GPU>, RAM <GB>
Tried and rejected: <change - result>
Undo: python3 $B/ls_entry.py rollback <backup from step 5>
```

## Gotchas
- `ls_entry.py add` backs up config.yaml, validates YAML and journals; llama-swap reloads on save. Saving does not
  stop other running models unless their entries changed.
- ubatch is measured with llama-bench while the model is unloaded:
  `llama-bench -m <gguf> -p 4096 -n 0 -ub 512,1024,2048`.

## Before you finish
- [ ] The user confirmed the plan; smoke test passed.
- [ ] Every kept change beat the baseline by > ~3 % with no silent quality loss.
- [ ] sync_prompts.py ran; docs committed and pushed.
