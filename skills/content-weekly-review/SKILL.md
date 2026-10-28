---
name: content-weekly-review
description: Use when the user wants to know how their X posts or YouTube videos did, a weekly content review, or next week's content plan. Reads their analytics CSV exports and writes lessons plus a plan. Input - optional week (default this week).
---
# /content-weekly-review
**Goal:** one page: what worked, what did not, one experiment, next week's plan. **Output:**
`~/content/reviews/<YYYY-Www>.md`. `R="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/content-weekly-review/scripts/review.py"`

## Rules
1. Judge by medians and by what the user can change (format, hook, time, topic), not by one viral outlier.
2. Every lesson cites the number behind it. Small samples (< 5 posts of a kind) are "a hint", not a lesson.
3. Growth comes from the user's own replies, posts and videos. Never suggest follow trains, engagement pods, bought
   promotion or automated replies - those get accounts removed.

## Steps
1. Ask the user to export: X (analytics -> Content -> Export) and YouTube Studio (Analytics -> Advanced -> Content ->
   Export -> CSV, the 'Table data.csv'). Save them to `~/content/reviews/inbox/`.
2. `$R run` -> writes the review file with the numbers filled in and prints the summary. (Unknown CSV: `$R columns <file>`.)
3. Read last week's review (same folder) and check its experiment: did the number move?
4. Fill the four empty sections of the new review: what worked (3), what did not (2), one experiment (hypothesis +
   change + metric), next week's plan (counts per day + which backlog ideas: `ideas.py list --status new`).
5. Mark ideas: published ones `ideas.py set <id> published`; planned ones `planned`.

## Reply
```
Week <W>: X median <n> impressions (<+/-> vs last week); YouTube <views> views, <hours> h watch time
Worked: ...   Did not: ...   Experiment: ...
Plan: <n> posts/day, <n> replies/day by hand, video: <idea>, short: <idea>   Review: <path>
```

## Before you finish
- [ ] each lesson has a number
- [ ] last week's experiment evaluated
