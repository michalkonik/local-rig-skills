---
name: select-meaningful-information-from-text
description: Use when the user wants the key points of a long text or transcript ("summarise", "what matters in this") - TL;DR, ranked points, takeaways, claims to verify, skip map. A kept YouTube video becomes summary.md (investment, technical, or earning). Input - text or a .txt/.md path.
---
# /select-meaningful-information-from-text
**Goal:** notes that let someone act on the topic without reading or watching all of it. **Input:** the text, or a
path to a .txt/.md file (often from /transcript-youtube-video). **Output:** a notes .md file + a short reply.
`C=~/Desktop/github_repos/local-rig-skills/skills/select-meaningful-information-from-text/scripts/chunk_text.py`
`K=~/Desktop/github_repos/local-rig-skills/skills/select-meaningful-information-from-text/scripts/check_summary.py`
`LIB=~/Desktop/github_repos/videos-transcriptions`

## Rules
1. Read all of the input: every chunk in order, never only the first chunk or the index.
2. Use only facts from the input. Anything you add is an Open question, or a URL marked `(looked up)` on something the speaker already named.
3. Keep the reasoning ("because") and keep numbers exact.
4. Write in the input's language unless the user asks otherwise.
5. A doubtful proper noun stays as heard. Check the transcript's `## Description` before guessing a cleaner name. If it is still unclear, mark it `(unverified)`.

## Steps
1. `python3 $C <file>` (pasted text: `python3 $C - <<'EOF' ... EOF`) -> prints size, the notes path
   (`<input>.notes.md`, or `~/Documents/notes/` for pasted text) and, for long inputs, chunks `c01..` with
   timestamp ranges in `<input>.chunks/`. Short input: read the file whole.
2. Per chunk, write terse working notes. Extract only: claims, numbers, definitions, mechanisms (how/why), how-tos
   and steps, warnings and failure modes, predictions, contrarian or surprising ideas. Each: one line, the
   speaker's reason or evidence, `[mm:ss]` or section, and a quote under ~15 words only when the wording matters.
   Skip greetings, recaps, sponsors, self-promotion, calls to subscribe, tangents with no payoff.
3. Merge duplicates across chunks (the overlap repeats boundary text); keep the clearest version + all timestamps.
4. Rank by importance (core to the topic) > novelty (not common knowledge) > actionability. Count: ~5 points for
   10 min / 2k words, ~10-15 for an hour, 20 max. Mark unsupported, opinion, outdated or doubtful claims
   `(unverified)` / `(speaker's opinion)`.
5. If the file is a `transcript.md` inside `$LIB` (a kept video), read `$LIB/README.md` and write `summary.md` in that same folder. That README is the only copy of the kind table and the section list. Then `python3 $K <summary.md>` must print `OK`. Do not also write `<input>.notes.md`.
6. Otherwise write the notes path in exactly this shape:
```
# <title> - key points
Source: <path or URL>, <length>, <date>
## TL;DR            3-5 lines: what it is about and the main conclusion
## Key points       numbered, ranked: **point** - why it matters - evidence/reasoning [mm:ss]
## Actionable takeaways   what the reader can do or use, concrete
## Open questions / claims to verify
## Skip/skim map    | part [from-to] | content | watch / skim / skip |
```
7. Move the `.chunks/` folder to the trash: `gio trash <input>.chunks`.
8. Reply with the template below.

## Reply
```
<TL;DR, 3-5 lines>
Notes: <notes path or summary.md>
<one line only if the input was thin or mostly filler>
```

## Before you finish
- [ ] Every chunk was read.
- [ ] No fact is missing from the input; doubtful claims are marked.
- [ ] A kept video's `check_summary.py` printed OK, and the `.chunks/` folder is in the trash.
