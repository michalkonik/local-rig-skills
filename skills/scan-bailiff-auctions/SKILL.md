---
name: scan-bailiff-auctions
description: Use when the user wants cheap items from Polish bailiff auctions (licytacje komornicze, e-licytacje) - cars, tools, electronics - ranked by discount to the appraisal, with deposit and dates. Reads the public portal; the user decides and bids. Input - category, voivodeship, max price.
---
# /scan-bailiff-auctions
**Goal:** a ranked shortlist of live bailiff auctions with discount, deposit (rękojmia) and dates.
**Output:** `~/income/bailiff/shortlist-<date>.md` (+ `shortlist-latest.json`); chosen items logged in the ledger.
`A="python3 $HOME/Desktop/github_repos/local-rig-skills/skills/scan-bailiff-auctions/scripts/auctions.py"`

## Rules
1. Read public listings only. Never log in, register, pay a deposit or bid: the user does that with their own
   PESEL and account.
2. Default budget rule from the course: appraisal under 5,000 PLN (no deposit for movables, low loss).
   Raise `--max-estimate` only when the user asks.
3. Discount, term, deposit and dates come from the script. Resale price, transport and defects are estimates you
   must label as such.

## Steps
1. Collect: category (default `movable`; specific ones from `$A categories`, e.g. `CARS,COMPUTER`), voivodeship
   (default: the user's), max opening price.
2. `$A scan --category CARS --province mazowieckie --max-price 4000` (add `--pages 1` for a quick look).
3. For the top 5, open each URL from the shortlist only if the user asks for details; the item page loads in a
   browser (it is not readable by script).
4. For each candidate the user likes, list what to check by hand: comparable prices on OLX/Allegro (the user
   pastes them), viewing date, transport, defects in the notice, documents (VIN, registration) and co-ownership.
5. When the user decides: `$A record <id> shortlisted|bid|bought|sold|lost --cost <price+fees> --revenue <sale>`.

Read `~/Desktop/github_repos/local-rig-skills/skills/scan-bailiff-auctions/reference.md` only when the user asks
why a price, deposit or term is what it is.

## Reply
```
<n> live auctions match (<k> new). Top:
1. <discount>% <opening>/<appraisal> PLN - <term> - deposit <x> PLN by <date> - <date start> - <place> - <url>
Next: compare resale prices and see the item before bidding. You pay the deposit and bid yourself.
```

## Gotchas
- 1st term: opening = 3/4 of the appraisal; 2nd term: 1/2 for movables, 2/3 for real estate. The real gap is at
  the 2nd term.
- Deposit = 1/10 of the appraisal; none for movables appraised under 5,000 PLN. For e-auctions it must reach the
  bailiff's account 2 working days before the start; "(est.)" dates are computed, the notice is binding.
- Listings whose deposit deadline has passed or that are no longer joinable are dropped.
- Real estate needs a 1/10 deposit of the full appraisal: far beyond the course budget.
- Buying to resell is business-like: watch the 10,813.50 PLN per quarter unregistered-activity limit
  (`ledger.py summary` shows it).
- If the portal ever blocks scripts, save the search page in a browser and run `$A scan --file <saved.html>`.

## Before you finish
- [ ] the user knows they bid and pay the deposit themselves
- [ ] resale estimates marked as estimates
