---
name: claim-money-owed
description: Use when the user wants money they are owed - a delayed, cancelled or overbooked flight (EU261 compensation), a faulty product, an online return or a price guarantee. Checks eligibility, drafts EN+PL letters, tracks deadlines. Input - flight details or the purchase.
---
# /claim-money-owed
**Goal:** a correct, ready-to-send claim letter and its deadlines, for the user's own claims only.
**Output:** `~/income/claims/<id>/` with `claim.json`, `letter-en.md`, `letter-pl.md`; the claim is logged in the ledger.
`C="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/claim-money-owed/scripts/claim.py"`

## Rules
1. Only the user's own claims. Filing for other people for a fee is a regulated business: decline it.
2. The user sends every letter. You draft, check and track; you never send, sign or submit.
3. Amounts, distances and deadlines come from the script output. Do not compute them yourself.
4. Bookings, names and bank details stay on the rig. Leave the `[PLACEHOLDERS]` for the user to fill.

## Steps
1. Collect the facts: from/to airports (IATA), connection airport, flight date and number, airline, what happened
   (delay at arrival in hours / cancellation with days of notice / denied boarding), any rerouting times, and the
   reason the airline gave. Ask only for what is missing.
2. Map the airline's reason to `--reason`: technical, crew, own-strike, overbooking, operational, weather, atc,
   atc-strike, airport-strike, bird-strike, security, political, medical, unknown (default when none was given).
3. Run `$C eu261 --from WAW --to BCN --date 2026-08-14 --type delay --delay-h 3.5 --reason technical --flight LO123 --carrier "LOT"`.
   Add `--via FRA` for one booking with a connection, `--eu-carrier yes|no` for flights into the EU from outside,
   `--notice-days N` for cancellations, `--reroute-early-h/--reroute-late-h` when rerouted.
4. `NOT ELIGIBLE` -> report the reason line and stop. `WARN CHECK` -> tell the user what is uncertain (the line
   starting with "-") before they send anything.
5. For shop cases run `$C letter --kind withdrawal|nonconformity|price-guarantee --shop "..." --item "..." --date YYYY-MM-DD --amount N`.
6. Read the letter files back and fix wording only (never the amount or legal basis). Tell the user which
   `[PLACEHOLDERS]` to fill.
7. When the user says they sent it: `$C sent <id>` (starts the 30-day answer clock and logs it in the ledger).
8. When the answer arrives: `$C outcome <id> paid --amount 400 --currency EUR` or `$C outcome <id> refused`.
   After a refusal or 30 days of silence, draft the complaint to the body named in the letter (for departures from
   Poland: Rzecznik Praw Pasażerów at ULC, form on ulc.gov.pl) within the dates `sent` printed.

Read `~/Desktop/github_repos/local-rig-skills/skills/claim-money-owed/reference.md` only when the user asks why a rule applies or which court
case or article supports it.

## Reply
```
<route> <km> km: <ELIGIBLE EUR n | CHECK | NOT ELIGIBLE> - <one-line reason>
Deadline: send by <date> (limit <date>, art. 205c ust. 7 Prawo lotnicze)
Letters: <path>/letter-en.md, letter-pl.md - fill: <placeholders>. You send it; then tell me "sent".
```

## Gotchas
- The 3-hour threshold is arrival delay measured when the doors open, not departure delay.
- Polish law gives 1 year from the flight (suspended while the airline handles the complaint, max 30 days).
  Other countries allow longer; the script plans with the shortest one.
- Intra-EU flights over 1,500 km are always EUR 400, even above 3,500 km.
- UK departures are UK261, not EU261. Flights into the EU on a non-EU airline are not covered.
- `list` shows every claim with its next date; the weekly review picks those up.

## Before you finish
- [ ] amount, km and deadlines copied from the script output
- [ ] the user knows they send the letter themselves
- [ ] `sent` recorded once the user confirms sending
