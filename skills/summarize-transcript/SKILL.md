---
name: summarize-transcript
description: Use when the user wants a transcript summarized (YouTube, talk, interview, meeting) - thesis, ranked points with [mm:ss], what to do, claims to check, and a skip map, saved as .summary.md. Not a general document summary. Input - a transcript path or pasted transcript.
---
# /summarize-transcript
**Goal:** a summary that replaces watching or listening. **Input:** a transcript, usually the Markdown file from
`/transcript-youtube-video` (title, channel, date, URL, then `[mm:ss]` lines). A pasted transcript is fine.
**Output:** `<transcript>.summary.md` next to the file, plus a short reply. Not the whole summary in chat.
A kept video (`transcript.md` inside `~/Desktop/github_repos/videos-transcriptions`) is the exception: `summary.md` in that same folder.
`C=~/Desktop/github_repos/local-rig-skills/skills/summarize-transcript/scripts/chunk_transcript.py`
`K=~/Desktop/github_repos/local-rig-skills/skills/summarize-transcript/scripts/check_summary.py`

## Rules
1. This skill is for transcripts only. A paper, article, or notes file is the wrong job: say so and stop, unless the user explicitly says to treat that file as a transcript.
2. Read every chunk in order. Never stop at the first chunk or the index.
3. Use only what the speakers say. Your own knowledge goes only under "Check".
4. Keep numbers, names, and the reason ("because") exact. Write in the transcript's language.
5. Spoken junk is not content: greetings, "welcome back", subscribe plugs, sponsor reads, "as I said", and a point restated without a new fact. Collapse a repeated point to the clearest wording and keep every timestamp.
6. If the transcript names speakers, attribute the claim. Do not merge two speakers into one voice.
7. Do not invent timestamps. No `[mm:ss]` in the file: mark the point with a short quote instead, and say the transcript has no times.
8. You decide what matters after reading. Do not pick lines with a script that searches for words such as buy, sell, or DCA. `check_summary.py` only checks that a library summary has the sections its README names.

## Steps
1. `python3 $C <file>` (pasted text: `python3 $C - <<'EOF' ... EOF`). It prints size, timestamp count, the summary path, and, for a long transcript, chunks `c01..` with time ranges in `<file>.chunks/`. A short file: read it whole. If it reports `not a timestamped transcript`, apply rule 1 or rule 7.
2. From the top of the file, take title, channel, date, duration, URL, and language when those lines exist.
3. Per chunk, write terse working notes. Keep only: the claim, a number, a definition, a mechanism (how or why), a step, a warning, a prediction, or a surprising turn. Each line: the point, the speaker's evidence, `[mm:ss]`, the speaker if named, and a quote under ~15 words only when the wording is the point. Skip filler from rule 5.
4. Merge the same claim across chunks. The overlap repeats the boundary. Keep the clearest wording and all of its timestamps.
5. Rank by how much the talk depends on it, then by what is not obvious, then by what the viewer can do. About 5 points for 10 minutes, 10-15 for an hour, 20 max. Mark a guess, a prediction, or an unsourced number `(speaker's claim)`. Mark a contradiction inside the transcript `(contradicted at [mm:ss])`.
6. If the file is `transcript.md` inside `~/Desktop/github_repos/videos-transcriptions`, write `summary.md` in that folder. The section list is that repo's `README.md`, not the shape below. Then `python3 $K <summary.md>` must print `OK`. Do not also write `<file>.summary.md`.
7. Otherwise write the summary path in this shape:
```
# <title> - summary
Source: <URL or path> | <channel or speakers> | <duration> | <date> | <language>
## TL;DR
3-5 lines: what the talk answers, and the conclusion
## Thesis
one sentence: the claim the transcript is actually making
## Key points
numbered, ranked: **point** - why it matters - evidence [mm:ss] (Speaker)
## Do this
concrete steps the speakers told the viewer to take, or "none"
## Check
opinion, unsourced numbers, or claims another speaker disputes
## Skip map
| [from-to] | what is said | watch / skim / skip |
```
8. `gio trash <file>.chunks` when that folder exists.
9. Reply with the template below. Do not paste the summary.

## Reply
```
<TL;DR, 3-5 lines>
Summary: <path>
<one line if the transcript was mostly filler or had no timestamps>
```

## Before you finish
- [ ] Every chunk was read, in order, and the summary is that reading, not a keyword extract.
- [ ] Every factual line is in the transcript; doubtful lines are marked.
- [ ] Repeated points are one line, with every timestamp. Sponsor reads and greetings are in the skip map only.
- [ ] The `.chunks/` folder is in the trash. A library summary's `check_summary.py` printed OK.
