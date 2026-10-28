---
name: income-ledger
description: Use when the user logs an income attempt or result ("I sent the claim", "got paid 800 zł for the gig", "lost the bonus"), asks how a stream is doing, or wants to know what to stop. Shared SQLite ledger with kill-check. Not for the weekly report - use /income-weekly-review. Input - what happened.
---
# /income-ledger
**Goal:** every attempt in the four income streams is one ledger row, so keep/kill decisions use numbers.
**Output:** a row added or updated in `~/.local/state/rig-skills/income.db`, and a one-line confirmation.
`L="python3 $HOME/Desktop/github_repos/local-rig-skills/lib/ledger.py"`

## Rules
1. Streams are `claims`, `freelance`, `bank-promos`, `bailiff`. Use only statuses the script lists for a stream.
2. Log the user's own time in `--hours` (human hours, not agent hours). Ask if they did not say; 0.3 is a fair
   default for a sent letter or proposal.
3. Amounts in the original currency with `--currency EUR|USD`: the script converts at the NBP rate of the last
   business day before the date (the rule used for Polish tax).
4. A ToS warning, account flag or payout refused over a rules question is logged as status `flagged`. The
   kill-check then pauses that stream.

## Steps
1. If the event belongs to another skill's flow, prefer that skill's command (it logs for you):
   claims `claim.py sent|outcome`, promos `promos.py start|outcome`, gigs `gigs.py sent|outcome`,
   auctions `auctions.py record`.
2. Otherwise add a row: `$L add-attempt --stream freelance --item "<URL or short ref>" --status proposed --hours 0.3`.
3. For a result on an existing row, find it with `$L list --stream freelance` and run
   `$L update <id> --status paid --revenue 800` (add `--currency USD` for foreign payouts).
4. "How is it going?" -> `$L summary` (last 28 days) or `$L summary --month 2026-10`.
5. "What should I stop?" -> `$L kill-check` and report each verdict with its reason.
6. A stream the user decides to drop: `$L stream <name> --status killed` (or `paused`).

## Statuses
| stream | statuses |
|---|---|
| claims | drafted, sent, escalated, paid, refused, skipped |
| freelance | proposed, won, delivered, paid, lost, skipped |
| bank-promos | open, paid, lost, refused, skipped |
| bailiff | shortlisted, bid, bought, sold, lost, skipped |
| any | pending, flagged |

## Kill criteria (from the course, encoded in `KILL` in the script)
- claims: nothing eligible after the first week -> keep only the yearly PIT check.
- freelance: after 6 weeks and 60 proposals, net < 100 USD/month or > 3 h per job -> stop.
- bank-promos: two bonuses in a row lost/refused, or open offers for you < 1,500 PLN -> stop.
- bailiff: after 2 months and 3 purchases, net margin < 10% or items unsold > 60 days -> stop.
- all: 4 weeks below 30 USD/h with no upward trend, or 20 attempts with zero wins -> stop; flagged -> pause.

## Reply
```
Logged: <stream> #<id> <status> <amount PLN> (<hours> h)
<kill-check line for that stream, if it is not KEEP>
```

## Gotchas
- Amounts are stored in PLN; the original amount and NBP table are kept in the note.
- Bailiff resale counts toward the 10,813.50 PLN per-quarter unregistered-activity limit; `summary` shows it.
- The open-offers figure for bank promos comes from the last `promos.py fetch`.

## Before you finish
- [ ] the row has the user's hours and the right status
- [ ] foreign amounts were given with `--currency`
