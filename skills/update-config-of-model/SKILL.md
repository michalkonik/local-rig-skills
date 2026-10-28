---
name: update-config-of-model
description: Use when approved changes to an existing model's setup must be applied (llama-swap entry, compose vars, flags, sampling, context, GPUs, drafts) - one change at a time, smoke test, benchmark, keep what helps, roll back the rest. New models: /add-new-model-to-config. Input - model + approved changes.
---
# /update-config-of-model
**Goal:** each approved change applied, measured, and kept only if it helps. **Input:** model id/alias + the list of
changes the user approved (usually from /inspect-current-config-of-model). **Output:** updated entry, docs, report.
`B=~/Desktop/github_repos/local-rig-skills/bin`

## Rules
1. Are you this model? If the model you are changing is the one answering in this chat, saving its entry restarts
   you and ends the answer. Then explain the plan, make the edit your LAST action, and tell the user to run the
   measurement steps from another model (e.g. Gemma) or by hand.
2. One change per measurement. Edit config.yaml with `ls_entry.py` whenever it can do the change (it backs up);
   if you must edit compose files, first `cp FILE FILE.bak-$(date +%Y%m%d-%H%M)`.
3. RAM >= 10 GB available before loading (`free -g`); if the model needs other models' cards:
   `curl -s localhost:8080/unload`.
4. Root only via the sudo approval tool: one command, with a reason.
5. Keep a change only without quality loss; never trade precision for speed silently.

## Steps
1. Read `~/Desktop/github_repos/local-rig-skills/reference/serving-playbook.md`.
2. Current entry: `python3 $B/model_report.py <id>`. No recent baseline? Run
   `$B/bg bench-<id>-base python3 $B/bench.py run <id> --label base`, poll `$B/bg bench-<id>-base`.
3. For each approved change, in order:
   a. `python3 $B/ls_entry.py patch <id> "<exact old text>" "<new text>" --dry-run`, check the diff, run it for real
      (bigger rewrites: `replace <id> FILE`). Note the backup path. Compose variables live in the entry's `cmd`
      (e.g. `SEQS=8`) - same patch command. New file needed? Get it first with /download-llm.
   b. `$B/bg smoke-<id> python3 $B/smoke.py <id> [--vision]` -> must pass (answer, tool call, vision if it had it).
   c. `$B/bg bench-<id>-<n> python3 $B/bench.py run <id> --label <short-change-name>`, then
      `python3 $B/bench.py compare <base.json> <new.json>`.
   d. Keep if better by more than ~3 % (or equal speed with a real benefit like more context) and no quality loss;
      otherwise `python3 $B/ls_entry.py rollback <backup>` and record why it was rejected.
   e. A kept result becomes the baseline for the next change.
4. Write the new measured numbers and the date into the entry's comment block and `description` (patch).
5. `python3 ~/.config/llama-swap/tools/sync_prompts.py`.
6. `python3 ~/Desktop/github_repos/llm-private-education/tools/snapshot-configs.py`; add a dated line to the change
   log in `en/03-MODELS-AND-SERVING.md` and `pl/03-MODELE-I-SERWOWANIE.md` (what changed, before -> after, rejected
   ideas); commit and push `llm-private-education`.
7. Reply with the template below.

## Reply
```
| change | kept / rolled back | before | after | why |
Backups: <paths>
Undo: python3 $B/ls_entry.py rollback <backup>
```

## Before you finish
- [ ] Every change was measured alone; rejected ones are rolled back.
- [ ] Entry comment/description have the new numbers; sync_prompts.py ran; docs pushed.
