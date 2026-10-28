---
name: make-youtube-short
description: Use when the user wants a YouTube Short or a vertical 30-55 s clip - "make a short", "clip the best result", a teaser for a long video. One finding, burned captions, fully local. Input - idea id, finding, or a video slug to cut from.
---
# /make-youtube-short
**Goal:** one surprising, real result in under a minute that makes people want the full video.
**Output:** `~/content/videos/<slug>-short/out/video.mp4` (1080x1920, captions burned in).
`V="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/make-youtube-video/scripts/video.py"`

## Rules
1. One idea, one number, from a real capture (reuse the long video's `captures/` when cutting from it).
2. Beat 1 is the hook and already contains the result. No intro, no "in this video".
3. 80-125 spoken words (30-55 s; 129 words rendered 58 s). End with one line pointing to the full video or the next test.

## Steps
1. `$V new <slug>-short --short`
2. Copy or make the proof: `cp ~/content/videos/<long>/captures/* ~/content/videos/<slug>-short/captures/` or
   `$V capture <slug>-short <name> -- <command>`.
3. Write script.json with `"short": true` and 3-5 scenes: big (the number) -> terminal or chart (the proof) ->
   bullets (why / the fix) -> optional big (takeaway). Read `$V schema` if unsure.
4. `$V check <slug>-short` -> fix until clean (it warns outside 20-58 s).
5. `$V all <slug>-short`
6. Title: <= 50 chars, the result in it; put the long video's link in the description.

## Reply
```
Short: <path> (<s> s)   Title: "<title>"   Links to: <long video slug or none>
```

## Before you finish
- [ ] under 60 s, number on screen in the first 2 s
- [ ] the number traces to a capture
