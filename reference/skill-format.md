# Skill format v2 (house standard, Oct 2026)

Skills here run on **local models** (Qwen3.8-Flash-Next ~130 tok/s, Gemma 4 26B-A4B, Qwen3.6 35B-A3B) through Open WebUI,
the llama.cpp UI and OpenClaw. Every token a skill makes the model read or write costs real seconds, and small models
drop instructions as the count grows. The format follows the agentskills.io spec plus what the research says about
local models (sources: `llm-private-education`, chapter 05).

## The rules that matter most
1. **Scripts do the work; the skill drives the scripts.** Anything deterministic (parsing, maths, validation, API
   calls, file layout, multi-step sequences) goes into one script command that prints a short summary. A step done by
   a script cannot be skipped or hallucinated.
2. **Short body.** Target <= 6 KB (~1,500 tokens), hard cap 10 KB. Reference material goes into a file the skill names
   with an exact *when to read it* condition. One level deep only.
3. **Numbered checklist, <= 10 steps,** imperative, one action each, the exact command in backticks.
4. **Rules first, re-checked last.** <= 5 rules at the top, phrased positively ("use only flags shown by --help"),
   and a "Before you finish" checklist at the end that repeats the critical ones.
5. **Defaults, not menus.** Name the default choice; mention an alternative only with the condition for using it.
6. **Exact output template** when the reply has a fixed shape. No prose descriptions of formats.
7. **Enforce in code, not in capitals.** A forbidden action is refused by the script; the skill just says what to do.

## Template
```markdown
---
name: verb-object                    # = folder name, lowercase-hyphens
description: Use when the user wants ... (trigger words, examples). Not for ... - use /other-skill. Input - ...
---
# /verb-object
**Goal:** one sentence. **Input:** ... **Output:** what "done" looks like (files, reply).
`S=~/Desktop/github_repos/local-rig-skills/skills/verb-object/scripts`

## Rules
1. ...

## Steps
1. `python3 $S/tool.py check ...` -> stop and report if it prints ERROR.
2. ...

## Reply
<exact skeleton, <= 10 lines>

## Gotchas
- environment facts that defy assumptions (<= 6)

## Before you finish
- [ ] ... (2-4 checks)
```

## Description (the routing text)
- <= 300 characters. It is in every system prompt and the OpenClaw skill list, so every character is paid on every
  request.
- Starts with "Use when ..."; names the user's intent and 2-3 trigger phrases; states the boundary ("Not for X - use
  /y"); ends with "Input - ...".

## Scripts
- One entry script per skill with sub-commands (`check | plan | apply | all | status`), Python 3 stdlib unless a
  dependency is unavoidable. `--help` <= 15 lines with two examples.
- stdout = a compact summary (<= 15 lines) ending with a clear verdict line (`OK ...`, `ERROR ...`, `WARN ...`);
  progress goes to stderr; big results go to a file whose path is printed.
- Errors say what was wrong, the valid values, and the exact command to retry.
- Idempotent (re-running redoes only what changed). Destructive or outward actions need an explicit `--apply`.
- Exit codes: 0 ok, 1 error, 2 usage, 3 not found, 10 needs the user's confirmation.

## Prompt-cache hygiene (why some things live where they do)
The Qwen3.x-Next models are hybrid (DeltaNet + attention): llama.cpp can only reuse the cached prompt when it grows
at the end. Anything that changes (dates, live state, the skill list order) must be at the end of the system prompt
or in the user turn, never in the middle. `bin/sync_skills.py` keeps the catalog order stable (alphabetical) for
the same reason.

## Checking a skill
`python3 bin/sync_skills.py --check` validates name, description length, body size. Test new or changed skills
on the real model with 3 realistic requests before merging; skills written by a local model are reviewed by a human.
