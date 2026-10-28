---
name: content-ideas
description: Use when the user asks what to post or film next, wants content ideas, or a weekly content plan for X/YouTube about local LLMs and agents. Gathers rig activity and niche trends, adds scored ideas to the backlog. Input - optional focus or number of ideas.
---
# /content-ideas
**Goal:** 5-10 ideas only this user can make, because they use his rig's real results. **Output:** ideas added to
`~/content/ideas/backlog.md` + a short ranked list in the reply.
`S=~/Desktop/github_repos/local-rig-skills/skills/content-ideas/scripts/ideas.py`

## Rules
1. Every idea has evidence on this rig: a command to run, a benchmark file, a config, a failure. No evidence, no idea.
2. Trends are triggers, not content: "new model X is trending" becomes "X on 4x R9700: what fits, how fast".
3. Prefer formats that win in this niche: "I ran X on Y" results, head-to-head charts, day-0 release tests, data-backed
   contrarian takes, build-in-public failures, short clips of agents running locally.

## Steps
1. `python3 $S gather` -> prints the sources file path. Read that file once.
2. `python3 $S list --status new` -> skip ideas already in the backlog.
3. Pick 5-10 ideas. For each, score quickly: own-data (0-3) + timeliness (0-3) + audience pull (0-3); keep >= 5.
4. Add each: `python3 $S add --title "..." --angle "what MY rig shows that others cannot" --formats "x,thread,short,video"
   --hook "first line of the post/video" --evidence "exact command or file" --pillar "<one of channel.json pillars>"`.
5. For a release test, check it fits before proposing it: size vs 4x32 GB VRAM and 60 GB RAM (/download-llm knows).

## Reply
```
Top ideas (score, formats):
1. <title> (8/9; thread + short) - hook: "<hook>" - evidence: <command>
...
Next: /write-x-post <id>  or  /make-youtube-video <id>
```

## Gotchas
- Reddit JSON is blocked (403); the script uses the RSS feed. A failed source prints WARN and the rest still works.
- Rig activity comes from the change journal and git logs. Few items means: run an experiment first, then post.

## Before you finish
- [ ] each added idea has a real --evidence
- [ ] no duplicate titles (the script refuses them)
