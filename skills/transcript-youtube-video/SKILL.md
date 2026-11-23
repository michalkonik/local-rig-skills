---
name: transcript-youtube-video
description: Use when the user wants the transcript of a YouTube video saved ("transcribe this video", "get the subtitles") - Markdown with [mm:ss] timestamps from captions, or local Whisper when there are none. For a summary use /summarize-transcript. Input - URL or search phrase, language.
---
# /transcript-youtube-video
**Goal:** the full transcript saved as Markdown (title, channel, date, duration, URL, language, source; paragraphs
with [mm:ss] timestamps). **Input:** a URL or video name / search phrase, optionally a language ("in Polish") or
"use Whisper". **Output:** a file in `~/Documents/transcripts/` and a short reply.
`T=~/Desktop/github_repos/local-rig-skills/skills/transcript-youtube-video/scripts/yt_transcript.py`

## Rules
1. Personal use only: transcripts stay in `~/Documents/transcripts/`, never in a git repo.
2. Reply with the path and stats; the transcript itself stays in the file.
3. Upgrading yt-dlp needs the user's OK, and only to a release at least 2 weeks old (change `YTDLP_PIN`).

## Steps
1. Name, not URL? `python3 $T --pick-only "<phrase>"` - prints title | channel | date | duration | URL and which
   captions exist. Show that line; if it is clearly not the video they meant, refine the phrase or ask.
2. Transcribe: `python3 $T "<URL or phrase>" [--lang pl] [--whisper]`
   - Captions first (uploader subtitles in the original language, then YouTube auto-captions; rolling duplicates
     removed). No captions, or `--whisper` -> audio goes to Speaches Whisper.
   - `--lang xx`: matching subtitles, else auto-captions in xx, else Whisper with that language.
   - Whisper takes ~1/6 of the video length (84 s audio = 13 s). Over ~10 min of video with Whisper, run in the
     background: `~/Desktop/github_repos/local-rig-skills/bin/bg yt python3 $T "<URL>" --whisper`, poll `bin/bg yt`.
3. Reply with the template below.

## Reply
```
Saved: <path>
Source: captions (manual|auto) | whisper, language <xx>, <N> words
Summary? /summarize-transcript <path>
```

## Gotchas
- "yt-dlp failed ... Sign in to confirm" / "HTTP 403" = YouTube blocked or changed: tell the user (see rule 3).
  Age-restricted and members-only videos are not supported.
- "Speaches not reachable" -> `docker start speaches`. Speaches: `http://127.0.0.1:8001/v1`;
  `curl -s 127.0.0.1:8001/v1/models` lists the model (`deepdml/faster-whisper-large-v3-turbo-ct2`, CPU,
  10-min chunks, progress + ETA on stderr).
- Wrong auto-caption language (e.g. English video detected as Arabic) -> rerun with `--lang en`.
- yt-dlp 2026.8.19 (pinned) lives in `~/.local/share/rig-skills/venvs/yt-dlp` (created on first use), with node as
  its JS runtime. ffmpeg: system `/usr/bin/ffmpeg`; Playwright's minimal build `~/.cache/ms-playwright/ffmpeg-1011`
  only as a last resort; without ffmpeg the audio goes to Speaches in one piece.

## Before you finish
- [ ] The file is in `~/Documents/transcripts/` and the reply has path, source, language, word count.
- [ ] The transcript text is not pasted into the chat.
