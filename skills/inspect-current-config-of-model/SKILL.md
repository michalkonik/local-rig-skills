---
name: inspect-current-config-of-model
description: Use when the user asks how a model is set up on this rig or whether it could run faster or better ("audit gemma", "can qwen3.6 be faster") - reads the setup, researches online, proposes cited improvements. Applying them: /update-config-of-model. Input - model id or alias.
---
# /inspect-current-config-of-model
**Goal:** a cited, ranked list of improvements for one model (or a plain "nothing worth changing"). **Input:** a
llama-swap id, alias (`gemma`, `qwen3.8`, `qwen3.6`) or part of the name. **Output:** findings table; changes only
after approval. `B=~/Desktop/github_repos/local-rig-skills/bin`

## Rules
1. Read-only until the user approves a change.
2. Cite every online source with its URL and date. This rig's own measurements decide; other people's numbers are
   hints.
3. Do not re-propose an idea the playbook lists as measured and rejected unless something changed - then say what.
4. Mark every quality trade-off; RAM limit 60 GB; never GPU 4.

## Steps
1. `python3 $B/model_report.py <model>` - entry with comments, every flag explained, engine build and age, model
   files and facts, recorded measurements, unused levers.
2. Read `~/Desktop/github_repos/local-rig-skills/reference/serving-playbook.md` (what was measured and rejected).
3. Optional, if the model is not running and the user wants numbers now:
   `$B/bg bench-<id> python3 $B/bench.py run <id> --label inspect`.
4. Research with web search + fetch (Open WebUI: `web_search`, `fetch_url`; llama.cpp UI: `rig-web_web_search`,
   `rig-web_fetch_url`), in this order:
   a. Model card of the exact repo (Hugging Face): sampling, context, chat template fixes, known issues.
   b. Newer files: a re-upload or better quant (unsloth UD, bartowski, ggml-org), an MTP/draft head, mmproj, a newer
      model version that replaces this one (same size class).
   c. Engine: llama.cpp releases/PRs since the local build's date for this architecture (search
      "llama.cpp <arch> performance", GitHub `ggml-org/llama.cpp` releases, issues with "gfx1201"/"RDNA4"/"Vulkan");
      vLLM/radiance: newer image tags and their changelogs (StillDeadcode); ROCm/Vulkan driver notes for RDNA4.
   d. Other people's numbers on R9700/RX 9070 (gfx1201) or similar cards (Reddit r/LocalLLaMA, GitHub discussions).
   Skip sources older than the local setup unless they explain a flag.
5. Reply with the table below, best first; "safe now" separate from "experimental"; mention download size/time if
   a new file is needed.
6. Ask which proposals to apply (numbers). Only after an explicit yes: get new files via /download-llm, then follow
   `~/Desktop/github_repos/local-rig-skills/skills/update-config-of-model/SKILL.md` (/update-config-of-model) with
   the approved list (it measures before/after and rolls back what does not help).

## Reply
```
Current: <engine/build, GPUs, ctx, measured tok/s>
Safe now:
| # | Change (exact flag/file) | Why (source URL, date) | Expected effect (speed / quality / memory) | Risk | How we measure |
Experimental:
| # | ... same columns ... |
Which numbers should I apply?
```
If nothing is worth changing, say so plainly - that is a valid result.

## Before you finish
- [ ] Every proposal has a source with URL + date and a measurement plan.
- [ ] Quality trade-offs are marked; nothing was changed without a yes.
