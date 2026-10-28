---
name: content-voice
description: Use when the user wants their posts or scripts to sound like them - "learn my style", "update my voice", before the first /write-x-post. Builds ~/content/profile/voice.md from their own writing samples. Input - none, or new sample text/files.
---
# /content-voice
**Goal:** a voice profile that makes drafts read like the user wrote them. **Input:** the user's own writing
(pasted text or files). **Output:** `~/content/profile/voice.md` + `voice.json` (numbers the linter checks).
`S=~/Desktop/github_repos/local-rig-skills/skills/content-voice/scripts` · `L=~/Desktop/github_repos/local-rig-skills/lib`

## Rules
1. Use only the user's own writing as samples. Someone else's posts would copy their voice, not the user's.
2. Every statement in voice.md is backed by a quoted sample line or a measured number.
3. Keep voice.md under 60 lines - it is read before every draft.

## Steps
1. `python3 $L/content.py init` (creates ~/content once).
2. If the user pasted text, save it to `~/content/profile/samples/<date>-<source>.md` (blank line between pieces).
   Ask for more if `stats` says THIN: old posts, Slack/Discord messages, README intros, e-mails all work.
3. `python3 $S/voice.py stats` -> numbers (sentence length, lowercase starts, emoji, punctuation, openers).
4. `python3 $S/voice.py examples 10` -> real passages.
5. Write `~/content/profile/voice.md` with the template below. Fill "How I sound" from the examples, not from
   imagination. Keep their quirks (lowercase, short lines, dry humour, Polish-English phrasing) - quirks are what make
   text read as human.
6. Show the user voice.md and ask: "Is anything here not you?" Apply their corrections.

## voice.md template
```
# My voice (from N samples, M words, <date>)
## Numbers (voice.json)          median sentence N words; lowercase starts X%; emoji Y/post; em dash: never
## How I sound                   4-6 bullets, each with a quoted example
## What I talk about             my rig, what I measured, what broke, opinions I hold (with one example each)
## Words I use / never use       short lists
## Opinions I am known for       3-5 strong takes, the user's own words
```

## Before you finish
- [ ] voice.json exists (stats ran) and voice.md quotes real samples
- [ ] the user confirmed or corrected the profile
