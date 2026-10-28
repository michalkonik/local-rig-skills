# Serving playbook for this rig (read before adding or changing a model)

Rules learned by measurement on mkoniu-B850-AI-TOP (4x Radeon AI PRO R9700, gfx1201, 32 GB each; Ryzen 7 9700X;
60 GB RAM; ROCm 7.2.4). Full history and numbers: `~/Desktop/github_repos/llm-private-education/en/03-MODELS-AND-SERVING.md`.

## Hard limits (breaking these crashed or froze the machine)
- **RAM 60 GB is the binding limit, not VRAM.** Pinned host memory cannot be swapped: radiance TP4 pinned 53 GB and
  the system swapped; a test llama-server next to the loaded radiance model caused a kernel panic (28 Oct 2026).
  Before loading anything big: `free -g` (keep >= 10 GB available), unload others (`curl -s localhost:8080/unload`).
  One heavy thing at a time. Never `--mlock`. ComfyUI (port 8188) also uses RAM/VRAM when it works.
- **GPU index 4 is the iGPU** (2 GB, ~50x slower). Never put 4 in `HIP_VISIBLE_DEVICES` / `GGML_VK_VISIBLE_DEVICES`.
  Vulkan and ROCm numbering are the same here: 0-3 = R9700 (`llama-server --list-devices`).
- **GPU 0 drives the monitors** (~0.8-1 GB used). vLLM on GPU 0: `--gpu-memory-utilization` <= 0.94.
- PCIe links: GPU 0 x8, 1 x4, 2 x8, 3 x4 (Gen5). Pairs 0+1 and 2+3 are used for 2-card models.
- llama-swap `concurrencyLimit` default 10 per model -> request 11+ gets HTTP 429; raise it for agent pools.

## Engine choice
| Situation | Engine | Why |
|---|---|---|
| New GGUF model, 1 card, MoE | llama.cpp **Vulkan** build (`~/llama.cpp-0ce8cd1-vulkan`) | +18-28 % vs ROCm for MoE on one card (Qwen3.6, Gemma 4), +5 % dense |
| GGUF on 2-4 cards | llama.cpp **ROCm** build (`~/llama.cpp` 680a036, or `~/llama.cpp-e86f5fd` for the newest archs) | multi-card is better on ROCm |
| safetensors FP8/BF16, many parallel agents | vLLM Radiance fork (Docker, `~/.config/llama-swap/vllm/`) | continuous batching, MTP, FP8 is more precise than Q5 |
| Qwen3.8-Flash-Next | radiance (`.rad`) | llama.cpp is kernel-launch bound on this arch (45 vs 120-145 tok/s) |
| Gemma 4 | llama.cpp (vLLM fork has no Gemma 4 26B) | |
Check which llama.cpp build knows the architecture: `<build>/bin/llama-server --version`; newer archs may need the
newest build or a rebuild (`git pull && cmake --build build -j` in a NEW folder, keep the old one).

## llama.cpp entry checklist (copy the style of the existing entries)
1. Binary: Vulkan build for 1-card MoE, ROCm build otherwise. Keep the shared flags:
   `--port ${PORT} --jinja --agent -fa on --ui-config-file ~/.config/llama-swap/ui/<id>.json --tools all
   --mcp-servers-config ~/.config/llama-swap/tools/mcp-web.json --cors-origins http://192.168.0.39:8080,http://localhost:8080,http://127.0.0.1:8080`
   (sync_prompts.py writes the ui/<id>.json file - run it after adding the entry).
2. `-ngl 999`. Fewest cards that fit weights + KV + ~1.5 GB per card: more cards = more hops = slower generation.
3. Multi-card: `--split-mode layer` (default) with `--tensor-split` (commas!) tuned so no card runs out first;
   tensor/row split only if measured better.
4. Context: the model's native maximum if it fits; `--kv-unified --parallel 2` gives 2 slots sharing one pool.
   KV `q8_0` (`--cache-type-k q8_0 --cache-type-v q8_0`) halves KV memory with a small quality cost - prefer fewer
   tokens of f16 unless long context is the point; say which you chose.
5. `--ubatch-size`: measure 512/1024/2048 with llama-bench (prompt 4096) and take the smallest within 2 % of the best;
   default 512 was never best (+3 % to +57 %); too big hurts (DeepSeek 4096 was -58 % vs 1024). `--batch-size` >= ubatch.
6. Speculative decoding: MTP head when the uploader ships one (`-md mtp-*.gguf --spec-type draft-mtp
   --spec-draft-n-max 2..4`); add `ngram-mod` for code/tool work. Measured best n-max: Gemma 4 = 4, Qwen3.8 = 2.
   Exception: Qwen3.6 embedded MTP in llama.cpp is broken (34-40 vs 107 tok/s) - don't.
7. Vision: `--mmproj <mmproj-F16.gguf>` (F16 for Vulkan). sync_prompts.py then marks the model as seeing images.
8. Sampling = the vendor's recommendation from the model card (`--temp --top-p --top-k --min-p`).
9. `ttl: 600`, an `aliases` list, a `name` ("#N Model - role (engine, N GPU)") and a one-line `description`
   with measured speed, context, GPUs and what it is for (the UIs and the model's own prompt show it).
10. Huge files (> ~60 GB): `--load-mode dio` loads faster.

## Optimisation order (new entries; usual payoff, highest first)
Measure each with `bin/bench.py` (one change at a time, keep > ~3 %):
1. Vulkan vs ROCm build (1 card).
2. Speculative decoding (MTP n-max 2/3/4, + ngram-mod for code).
3. ubatch 512/1024/2048 (prompt speed - use `llama-bench -m <gguf> -p 4096 -n 0 -ub 512,1024,2048` while the model
   is unloaded).
4. Tensor split / fewer cards.
5. `--parallel` for multi-agent use.

## When a load fails
Read `curl -s localhost:8080/logs | tail -80` - llama.cpp prints why:
- unknown arch -> newer build;
- OOM -> fewer ctx / KV q8_0 / more cards;
- template errors -> `--chat-template-file` or a newer build.

## vLLM / radiance entries
Copy an existing entry and change the variables (`GPUS`, `TP`, `SEQS`, `KVDT`, `MAXLEN`, `CHAT_MODEL`, `MODELDIR`,
`RADFILE`). Compose files: `~/.config/llama-swap/vllm/*.compose.yml`, `~/.config/llama-swap/radiance/*.compose.yml`;
wrapper `run-compose.sh`. Lossless choices that cost nothing: KV bf16 (not uncalibrated fp8), radiance
`WIRE=exact`. radiance: TP2 only, `HOSTPOOL=8192`, `NGRAM=disk` (RAM!). Only one radiance model at a time.
Cold start of vLLM: 2-3 min (kernel cache `~/radiance-vllm-mxfp4/vllm-cache`).

## Groups
`groups:` decide which models may be loaded together. `duo` = qwen3.8-flash-next (GPU 0+1) + qwen3.6-35b-a3b
(GPU 2+3), `swap: false, exclusive: true`. A new model outside groups unloads everything when it loads (safe
default). Put models in one group only if their GPUs do not overlap AND their RAM fits together.

## Measuring (the only accepted evidence)
- Speed: `bin/bench.py run <id> --label before|after` (vendor sampling, chat + 14k code prompt, concurrency 1 and 4),
  then `bin/bench.py compare`. Run in the background with `bin/bg` (takes minutes). Compare rep 1 values; < 3 % is noise.
- It works: `bin/smoke.py <id> [--vision]` (load time, answer, tool call, image).
- Quality: never trade precision for speed silently (lower quant, KV q4, lossy wire formats). If a change can affect
  answers, say so and propose a check (same prompts before/after, or local-llm-quality-bench:
  `~/Desktop/github_repos/local-llm-quality-bench`, `python3 -m qbench run --model <profile> --k 3`).
- Write the measured numbers into the entry's comment and `description`.

## After any change
1. `python3 ~/.config/llama-swap/tools/sync_prompts.py` (prompts, llama.cpp UI defaults, Open WebUI model settings).
2. Snapshot + document: `python3 ~/Desktop/github_repos/llm-private-education/tools/snapshot-configs.py` and add a line
   to the model's section / change log in `llm-private-education` (EN + PL), then commit and push that repo.
3. The change journal: `~/.local/state/rig-skills/journal.log` (ls_entry.py writes it automatically).
