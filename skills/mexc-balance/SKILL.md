---
name: mexc-balance
description: Use when the user asks for the MEXC spot balance or how much of a coin is on MEXC. Read only. Not Gate, mBank, or PKO. Not history - use /mexc-transactions. Input - optional asset.
---
# /mexc-balance
**Goal:** report MEXC spot balances. **Input:** optional asset such as USDT. **Output:** the reply template. Nothing is written to disk.
`M="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/mexc.py"`

## Rules
1. Do not open the Bitwarden vault or print the key, secret, or signature. The script reads `mexc`.
2. Read only. Spot only. Do not place an order, transfer, or withdraw.
3. Quote figures from the script. Do not invent a balance.

## Steps
1. `$M balance`. One coin: `$M balance --asset USDT`.
2. If the script prints `ERROR`, stop and report that line.

## Reply
```
MEXC spot
- <asset> free <amount> locked <amount>
```

## Gotchas
- Zero balances are hidden. The OK line says how many assets were returned.
- Free and locked are both part of the spot balance. Report both.
- `Api key info invalid` means the key is not active yet or the IP whitelist does not match this machine. Do not invent a balance.

## Before you finish
- [ ] every figure came from the script in this run
- [ ] the reply has no key, secret, or signature
