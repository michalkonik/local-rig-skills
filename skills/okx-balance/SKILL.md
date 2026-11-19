---
name: okx-balance
description: Use when the user asks for the OKX balance or how much of a coin is on OKX. Read only. Not Gate or MEXC. Not history - use /okx-transactions. Input - optional currency.
---
# /okx-balance
**Goal:** report OKX trading-account and funding-account balances. **Input:** optional currency such as USDT. **Output:** the reply template. Nothing is written to disk.
`M="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/okx.py"`

## Rules
1. Do not open the Bitwarden vault or print the key, secret, passphrase, or signature. The script reads `okx`.
2. Read only. Do not place an order, transfer, or withdraw.
3. Quote figures from the script. Do not invent a balance.

## Steps
1. `$M balance`. One coin: `$M balance --ccy USDT`.
2. If the script prints `ERROR`, stop and report that line.

## Reply
```
OKX trading
- <ccy> available <amount> frozen <amount>
OKX funding
- <ccy> available <amount> frozen <amount>
```

## Gotchas
- Zero balances are hidden. Each OK line says how many currencies were returned.
- Trading and funding are separate. Report both.
- `50104` means the OKX passphrase is not stored. Ask for it. Do not invent a balance.
- A missing `User-Agent` makes OKX return Cloudflare `1010`. The script sends one.

## Before you finish
- [ ] every figure came from the script in this run
- [ ] the reply has no key, secret, passphrase, or signature
