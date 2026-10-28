---
name: make-youtube-video
description: Use when the user wants a YouTube video made - "make a video about", "turn this benchmark into a video", an idea id. Fully local - real terminal captures, narrated slides/charts/code, captions, chapters, thumbnail. Not for vertical shorts - use /make-youtube-short. Input - idea id or topic.
---
# /make-youtube-video
**Goal:** an 8-15 min educational video built on real results from this rig. **Output:** `~/content/videos/<slug>/out/`
with video.mp4, captions.srt, chapters.txt, thumbnail.png; next step /publish-youtube-video.
`V="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/make-youtube-video/scripts/video.py"`
`T="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/make-youtube-video/scripts/thumb.py"`

## Rules
1. Every number and terminal output on screen comes from a real run (`$V capture`) or a file on the rig. A video
   without new measurements is the "inauthentic content" YouTube demonetizes.
2. Narration is in the user's voice (`~/content/profile/voice.md`): first person, opinions, what surprised them,
   what broke. Spoken words, short sentences.
3. The first 30 s deliver what the title promises: the result first, then how.
4. Run one heavy job at a time: free RAM before big model runs (`free -g`; `curl -s localhost:8080/unload`).

## Steps
1. Facts: `ideas.py show <id>` (content-ideas skill) or the user's topic. List the claims the video makes and the
   command that proves each.
2. `$V new <slug>` then `$V schema` (read the scene format once).
3. Capture every proof: `$V capture <slug> <name> -- <command>` (benchmarks, configs, `free -g`, errors). Long runs:
   wrap with `~/Desktop/github_repos/local-rig-skills/bin/bg`.
4. Outline 6-10 chapters of 60-120 s: hook, setup, each finding, what broke, takeaway. Then write
   `~/content/videos/<slug>/script.json` (title, scenes). A visual change at least every ~20 s.
5. `$V check <slug>` -> fix every ERROR and WARN about tells, hook and length; repeat until clean.
6. Look at 2-3 key scenes before the full run: `$V frame <slug> <scene>` -> out/preview.png (attach/inspect).
7. `$V all <slug>` (TTS, frames, mp4; about 1 min per 10 min of video).
8. Thumbnail: `$T <slug> --text "3-4 WORDS, *accent*" --badge "<real number>" --bg assets/<photo>` (own photo or
   screenshot is best) or `--prompt "<scene>"` (ComfyUI) or `--frame <scene>`. Make a variant B with a different
   text for YouTube's Test & Compare: add `--variant B`.
9. Write 3 title options (<= 60 chars, the number or the stake in it) into `out/titles.md`.

## Reply
```
Video: <path>/out/video.mp4 (<mm:ss>, <n> chapters)  thumbnail A/B: <paths>
Titles: 1) ... 2) ... 3) ...
Proofs captured: <names>   Next: watch it once, then /publish-youtube-video <slug>
```

## Gotchas
- Kokoro mispronounces jargon; video.py fixes common terms. Add others to `pronounce` in ~/content/profile/channel.json.
- Hand-written terminal output must be marked `"illustrative": true` - prefer a real capture. A terminal scene may
  set `"cmd"` to a shorter command to show; capture readable output (summaries, `| tail -15`), not raw dumps.
- The voice is set in channel.json (`tts_voice`, Kokoro: am_michael, bm_george, am_fenrir...).

## Before you finish
- [ ] `$V check` clean; every chart/big number has `source`
- [ ] out/video.mp4 and thumbnail exist; titles written
- [ ] the user watches it before publishing
