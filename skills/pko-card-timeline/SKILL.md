---
name: pko-card-timeline
description: Use when the user asks how many days until PKO credit-card interest starts if they do not repay. Uses only a due date the bank feed returns. Not the balance alone - use /pko-balance. Input - none.
---
# /pko-card-timeline
**Goal:** say whether the PKO credit-card feed includes a repayment date, and how many days remain. **Input:** none. **Output:** the reply template.
`P="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/pko.py"`

## Rules
1. Do not open the vault or print tokens, keys, or a full account number.
2. Do not invent a grace period, a due date, or a day count. If the script says no due date, report that and stop.
3. Read only. Do not move money.

## Steps
1. `$P card`.
2. If the script prints `ERROR` or `OK no session`, stop and report that line.
3. Reply with the limit line and either the day count or the no-due-date line. Do not add a number the script did not print.

## Reply
```
PKO card <mask> limit <amount>
<balance lines>
Interest: <in N days on DATE | no due date in the bank feed>
```

## Gotchas
- Enable Banking does not have an interest-start field. The script counts days only when a balance name looks like a due date.
- A closing-balance date is not the interest date. The script ignores it on purpose.
- PKO's connector is marked beta.

## Before you finish
- [ ] the day count was printed by the script, or you said the feed has no due date
- [ ] the reply has no full account number, key, or token
