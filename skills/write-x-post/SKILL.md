---
name: write-x-post
description: Use when the user wants one English X draft from a content idea, into ~/content/x/queue. Not the two-account daily operator - use /x-operate. Input - idea id, topic or post URL.
---
# /write-x-post
**Goal:** a draft that reads like the user on a good day: specific, opinionated, with a real number.
**Output:** a file in `~/content/x/queue/` that passes `xq.py check`; the user copies and posts it.
`S=~/Desktop/github_repos/local-rig-skills/skills/write-x-post/scripts/xq.py`

## Rules
1. Read `~/content/profile/voice.md` first and write in that voice. (No voice.md yet -> run /content-voice first.)
2. Numbers come from the rig: run the command or read the file named in the idea's evidence. Never estimate a number.
3. The user posts and replies by hand. X removes accounts that post or reply through bots or browser automation.
4. One idea per post. The first line carries the result or the tension, not a teaser.
5. The two-account day loop is /x-operate. This skill does not pick the account or the day's replies.

## Steps
1. Get the facts: `python3 ~/Desktop/github_repos/local-rig-skills/skills/content-ideas/scripts/ideas.py show <id>`
   and run its evidence command (or read the file). For a reply: `python3 $S fetch <URL>`.
2. `python3 $S new post|thread|reply <slug> --idea <id> [--reply-to URL]` -> prints the file path.
3. Write the draft into that file (after the front matter). Shapes:
   - post: result first ("Qwen3.8 on 2 R9700s: 132 tok/s at 128k context."), then why it matters or what surprised you,
     then optionally a question people want to answer. <= 280 chars unless channel.json has x_premium.
   - thread: post 1 = hook + the headline number; 2-N = method, numbers, what broke, the config line; last = takeaway
     + link (links only in the last post). Separate posts with a line `---`.
   - reply: 1-3 sentences that add something only the user has: a datapoint from the rig, a correction, a config tip.
4. `python3 $S check <file>` -> fix every FIX line and re-run until OK. If it still fails after 3 rounds, show the
   user the draft and the remaining FIX lines.
5. Write 2 alternative first lines below the draft as `<!-- alt: ... -->` comments, so the user can pick.

## Reply
```
Draft: <path>  (<kind>, <n> chars, check OK)
<the draft text>
Post it yourself, then: python3 xq.py posted <path> --url <link>
```

## Gotchas
- Media sells on X: suggest the chart or terminal screenshot to attach (frames from a video project work).
- Replies within the first hour of a big niche account's post get seen; replies to old posts mostly do not.

## Before you finish
- [ ] every number traced to a command or file
- [ ] `xq.py check` printed OK
- [ ] nothing was posted by you
