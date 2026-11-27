---
name: transcript-youtube-video
description: Use when the user wants a YouTube transcript saved ("transcribe this video", "get the subtitles") - Markdown with [mm:ss] from captions, or local Whisper when none exist. A kept video goes in repo videos-transcriptions. Next /select-meaningful-information-from-text. Input - URL or name, language.
---
# /transcript-youtube-video
**Goal:** the full transcript as Markdown (title block, `[mm:ss]` paragraphs, uploader description kept separate).
**Input:** a URL or video name, optionally a language ("in Polish") or "use Whisper". **Output:** one file and a short reply.
`T=~/Desktop/github_repos/local-rig-skills/skills/transcript-youtube-video/scripts/yt_transcript.py`

## Rules
1. Personal use only. A one-off transcript goes to `~/Documents/transcripts/` and is not committed. A video the user wants kept goes only in the private repo `michalkonik/videos-transcriptions`, via `--library`. No other git repo.
2. Reply with the path and stats. The transcript stays in the file.
3. Upgrading yt-dlp needs the user's OK, and only to a release at least 2 weeks old (change `YTDLP_PIN`).
4. Do not commit or push the library unless the user asks.

## Steps
1. Name, not URL? `python3 $T --pick-only "<phrase>"` prints title | channel | date | duration | URL and which captions exist. Show that line. If it is clearly the wrong video, refine the phrase or ask.
2. Kept video (save it for later, summarise it for action, or they name the library): `python3 $T "<URL>" --library [--lang pl] [--whisper]`
   One-off: `python3 $T "<URL or phrase>" [--lang pl] [--whisper]`
   - Captions first (uploader subtitles in the original language, then YouTube auto-captions; rolling duplicates removed). No captions, or `--whisper`, sends the audio to Speaches Whisper.
   - `--lang xx`: matching subtitles, else auto-captions in xx, else Whisper in that language.
   - Whisper takes ~1/6 of the video length (84 s audio = 13 s). Over ~10 min of video with Whisper, run in the background: `~/Desktop/github_repos/local-rig-skills/bin/bg yt python3 $T "<URL>" --whisper`, poll `bin/bg yt`. Add `--library` on that command when the video is kept.
   - `--library` writes `channels/<slug>/<date>--<id>--<title>/transcript.md` and creates `CHANNEL.md` for a new channel. Paths and slugs are the script's. The summary shape is that repo's `README.md`. If the clone is missing, the script prints the `gh repo clone` command. Run it and retry.
3. For a kept video, run `/select-meaningful-information-from-text` on that `transcript.md`.
4. Reply with the template below.

## Reply
```
Saved: <path>
Source: captions (manual|auto) | whisper, language <xx>, <N> words
Key points? /select-meaningful-information-from-text <path>
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
- [ ] The one-off file is in `~/Documents/transcripts/`, or the kept video is only `transcript.md` from `--library`.
- [ ] The reply has path, source, language, and word count.
- [ ] The transcript text is not pasted into the chat.
