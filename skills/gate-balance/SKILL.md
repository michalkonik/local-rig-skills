---
name: gate-balance
description: Use when the user asks for the Gate.io spot balance or how much of a coin is on Gate. Read only. Not mBank or PKO. Not history - use /gate-transactions. Input - optional currency.
---
# /gate-balance
**Goal:** report Gate.io spot balances. **Input:** optional currency such as USDT. **Output:** the reply template. Nothing is written to disk.
`G="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/gate.py"`

## Rules
1. Do not open the Bitwarden vault or print the key, secret, or signature. The script reads `gateio`.
2. Read only. Do not place an order, transfer, or withdraw.
3. Quote figures from the script. Do not invent a balance.

## Steps
1. `$G balance`. One coin: `$G balance --currency USDT`.
2. If the script prints `ERROR`, stop and report that line.

## Reply
```
Gate spot
- <currency> available <amount> locked <amount>
```

## Gotchas
- Zero balances are hidden. The OK line says how many currencies were returned.
- Locked and available are both part of the spot balance. Report both.
- The key is read-only and tied to this machine's public IP. An IP error means the whitelist changed, not that the coin is missing.

## Before you finish
- [ ] every figure came from the script in this run
- [ ] the reply has no key, secret, or signature
