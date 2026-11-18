---
name: pko-balance
description: Use when the user asks for the PKO balance, saldo, or credit-card limit. Reads Enable Banking. Not mBank - use /read-mbank-balance. Not history - use /pko-transactions. Input - optional account hint.
---
# /pko-balance
**Goal:** report PKO balances for the consented accounts. **Input:** optional account hint. **Output:** the reply template. Nothing is written to disk.
`P="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/pko.py"`

## Rules
1. Do not open the Bitwarden vault or print tokens, keys, or a full account number. The script reads `enablebanking-pko`.
2. Read only. Do not start a payment or call `auth` unless the script says there is no session and the user asked to connect.
3. Quote figures from the script. Do not invent a balance.

## Steps
1. `$P status`. If it prints `OK no session`, stop and report that line plus the WARN about the redirect.
2. `$P balance`. One account: `$P balance --account HINT`.
3. If the script prints `ERROR`, stop and report that line.

## Reply
```
PKO <type> <mask>
- <balance name> <amount> <currency> (ref <date>)
```

## Gotchas
- Linking the account in the Enable Banking control panel only activates the app. Balances need `pko.py session` after a redirect you control.
- The registered redirect must not be `example.com`. That host would receive the bank code.
- PKO's connector is marked beta.

## Before you finish
- [ ] every figure came from the script in this run
- [ ] the reply has no full account number, key, or token
