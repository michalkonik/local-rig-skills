---
name: publish-youtube-video
description: Use when a finished video project should go to YouTube - "upload it", "schedule the video for Tuesday". Uploads through the official YouTube Data API as private or scheduled, with thumbnail, captions and chapters. Input - video slug and optional publish time.
---
# /publish-youtube-video
**Goal:** the video on the user's channel, private or scheduled, with metadata done. **Output:** the YouTube link
and Studio link. `Y="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/publish-youtube-video/scripts/yt.py"`

## Rules
1. Upload as `private` (default) or scheduled (`publishAt`, private until then). Making it public is the user's
   click in Studio unless they said otherwise.
2. Set `containsSyntheticMedia` honestly: **true** only if the video shows realistic generated people, places or
   events, or a voice that imitates a real person other than the user. **false** for AI-written scripts, Kokoro
   narration, slides, charts, terminal captures, the user's own cloned voice (YouTube's disclosure rules, 2026).
3. Description: what the viewer gets with the key number, hardware and versions, chapters (from chapters.txt),
   links. Same voice as the video. No keyword stuffing.

## Steps
1. `$Y setup-check` -> if the client or token is missing, follow the one-time setup below and stop until done.
2. `$Y meta <slug>` -> fill `~/content/videos/<slug>/out/metadata.json`: title (pick from out/titles.md), description,
   5-12 tags (model, GPU, engine names), containsSyntheticMedia, publishAt (UTC, e.g. 2026-11-05T15:00:00Z) if
   scheduled.
3. `$Y check <slug>` -> fix every ERROR.
4. `$Y upload <slug> --dry-run` -> show the user the title/description/flags; upload after they agree.
5. `$Y upload <slug>` (re-run is safe: it continues where it stopped).

## One-time setup (the user does this, ~10 min)
1. Google Cloud Console -> new project -> enable "YouTube Data API v3" -> OAuth consent screen (External, add own
   account as test user, then "Publish app" so tokens do not expire after 7 days) -> Credentials -> OAuth client ID
   -> Desktop app -> download JSON to `~/content/profile/youtube-client.json`.
2. `$Y auth-url` -> open the link, approve -> copy the address the browser ends on -> `$Y auth-code "<address>"`.
3. Uploads from an unaudited API project may be **locked private** (Google's docs disagree, Oct 2026): test one
   private upload first. If it is locked, publish each video by hand in Studio (fine for 1-2 a week) or request the
   free YouTube API audit (Google form "YouTube API Services - Audit").

## Reply
```
Uploaded: https://youtu.be/<id> (<private|scheduled for ...>)  Studio: <link>
Thumbnail <ok>, captions <ok>. In Studio: add the B thumbnail/title to Test & Compare, check the end screen.
```

## Before you finish
- [ ] the user saw the dry run
- [ ] containsSyntheticMedia decided with rule 2
