---
name: x-operate
description: Use when running the two X accounts - morning brief, audit of what Michał did, who to talk to, follow or unfollow, or a draft. He posts by hand. Not the content-idea queue - use /write-x-post. Input - none, or a post URL.
---
# /x-operate
**Goal:** manage both accounts. Correct missed, extra, and wrong moves, then leave drafts. **Output:** `out/TODAY.md` at 06:00, `out/NEXT.md` on later wakes.
`S=~/Desktop/github_repos/local-rig-skills/skills/x-operate/scripts/xmgr.py`

Strategy lives in `~/Desktop/komunikacja-x/`. This skill does not restate it. Follower counts in those files are stale. The live profile wins.

## Rules
1. You write files. Michał posts. Never click Post, Reply, Like, Follow, or Repost, and never type into the X composer.
2. A number in a draft comes from `--evidence` (a file that exists) or from the post you are answering. No estimated tok/s, watts, or dates.
3. `@local_agents` is the international account, English, including Polish people who post the work in English. `@youroldpalhorse` is Polish only. The same person is not contacted from both accounts in one week.
4. Judge a person from a post you opened. Interesting: own number or own build, and they answer a technical reply. Farmer: quote-tweets, tool lists, "thoughts?", follow-for-follow, or no original fact in the last 10 posts. Never draft a reply to a farmer.
5. Create people, audits, engagement, rules, and drafts only with `xmgr.py`. If it prints ERROR, drop the idea. Read `/x-voice` before the draft text.

## Steps
1. `python3 $S wake`. Open both profiles and yesterday's posts before any draft.
2. Record what he missed, overdid, or broke, and what worked: `python3 $S audit miss|too-much|wrong|worked --note "..." [--account ACCOUNT]`.
3. For each person worth a decision: `python3 $S person HANDLE --verdict interesting|farmer|watch --circle intl|pl --seen URL --why "the fact" [--suggest talk|follow|unfollow]`. Close a done one with `--close`.
4. Record the counts you just saw: `python3 $S engage ACCOUNT --followers N --following N [--views N] [--author-replied yes|no|none]`.
5. One plan change at most, and only with a number: `python3 $S rule "what changes" --because "the count or id"`. Leave `STRATEGIA.md` alone. It stays proposed until Michał says keep.
6. Then drafts: `fetch`, `new`, `check` until OK. On a brief, replace every FILL. A scan audits only if he posted off-plan since the brief.

## Reply
```
File: <TODAY.md or NEXT.md>
Audit: <missed / too much / wrong, or none>
Talk: <@handle why>   Follow: <@handle>   Unfollow: <@handle>
Proposals: <id> <@account> — <first line>
Plan: <none, or the proposed rule id>
Nothing posted. Nothing followed.
```

## Gotchas
- Week 1 starts Monday 2026-11-16. Before that, `new post` is an ERROR. First English pin is Tue 2026-11-17 16:30. First Polish post is Wed 2026-11-18 19:00.
- Browser is for reading Latest, profiles, and threads. Two accounts: do not switch by posting.
- Headers, avatars, and the GitHub link were set by Michał on 12 Nov 2026. Do not propose replacing them. The Polish bio's second sentence (the motivational line) may be flagged once, then dropped if he keeps it.

## Before you finish
- [ ] Audit is filled from the live accounts, or explicitly NONE
- [ ] every talk, follow, and unfollow has a post URL and a verdict
- [ ] `xmgr.py check` printed OK for every new proposal
- [ ] no post, reply, like, follow, unfollow, or repost was sent
- [ ] TODAY.md or NEXT.md has no FILL left
