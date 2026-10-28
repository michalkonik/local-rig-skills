---
name: income-weekly-review
description: Use when the user wants the weekly income review, "how did my side income do this week", or a keep/kill decision across claims, freelance gigs, bank promos and bailiff auctions. Writes ~/income/reviews/YYYY-Www.md from the ledger. Input - optional week (default this week).
---
# /income-weekly-review
**Goal:** a 20-minute Sunday review: net per hour per stream, the kill-check, deadlines, and the decisions.
**Output:** `~/income/reviews/<YYYY-Www>.md` with the numbers filled in and the "Decisions" section written.
`W="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/income-weekly-review/scripts/weekly_review.py"`

## Rules
1. Judge streams by net PLN per hour of the user's time over 4 weeks, not by one good or bad week.
2. Every decision cites a number from the review file or a kill-check line.
3. A KILL verdict is a recommendation; the user decides. PAUSE (a ToS flag) means stop using that platform until
   the user has read its terms.

## Steps
1. Ask the user whether any result is missing from the ledger (payments received, bonuses, sold items). Log them
   with /income-ledger first.
2. Refresh inputs that feed the deadlines: `python3 ~/Desktop/github_repos/local-rig-skills/skills/track-bank-promotions/scripts/promos.py due --days 21`
   (no network) and, if the user tracks auctions, the last shortlist is read as is.
3. `$W run` (or `$W run --week 2026-W44`) -> writes the review file and prints the summary.
4. Read last week's review (same folder) and check its "One change for next week": did the number move?
5. Fill the "## Decisions" section of the new file, in this order (course 02 §4):
   - Move hours toward: the top row by PLN/h, if it has at least 2 attempts.
   - Stop / pause: every KILL or PAUSE line, with the reason.
   - Win rate vs what I expected: wins / attempts per stream.
   - One change for next week: one concrete action with the number it should move.
6. Re-running `$W run` refreshes the numbers and keeps the Decisions section.

## Reply
```
Week <W>: net <n> PLN over 4 weeks; best <stream> <n> PLN/h; worst <stream> <n> PLN/h
Kill-check: <stream VERDICT reason> (one line per non-KEEP stream)
Next 3 weeks: <up to 3 deadlines>
Decision: <one line>. Review: <path>
```

## Gotchas
- Streams in their test period show EXTEND; that is expected for the first 1-9 weeks.
- PLN/h is empty when no hours were logged; ask the user for rough hours instead of guessing.
- Deadlines come from `~/income/claims/*/claim.json`, `~/income/bank-promos/checklists.json` and the last
  bailiff shortlist; a stale shortlist shows old auctions.

## Before you finish
- [ ] missing results logged before running the review
- [ ] Decisions section filled, each line with a number
