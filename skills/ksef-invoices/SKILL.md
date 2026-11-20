---
name: ksef-invoices
description: Use when the user wants Firehorse KSeF invoices listed or downloaded as XML. Sales are invoices the company issued. Costs are invoices it received. Does not issue an invoice. Input - from and to dates, optional subject.
---
# /ksef-invoices
**Goal:** list or download Firehorse IT Consulting e-invoices from KSeF. **Input:** `--from` and `--to` as YYYY-MM-DD, optional `--subject sales|costs|both`. **Output:** the script's `OK` line and the rows or file counts.
`K="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/ksef.py"`

## Rules
1. Do not print the token. The script reads `bw-secret ksef#token` and `bw-secret ksef#nip`.
2. List and download only. Do not issue or send an invoice.
3. Quote counts and rows from the script. Do not invent an invoice.
4. `--page-size` must be 10..250. The default 100 is valid.

## Steps
1. List: `$K list --from YYYY-MM-DD --to YYYY-MM-DD --subject sales`. Use `costs` for invoices the company received, or `both`.
2. Download: `$K download --from YYYY-MM-DD --to YYYY-MM-DD --subject both --out ~/Documents/ksef/6891205697`.
3. If the script prints `ERROR`, stop and report that line.

## Reply
```
KSeF <sales|costs|both> <from>..<to>
OK list <n>
```
or
```
OK download saved=<n> skipped=<n> failed=<n>
```

## Gotchas
- `sales` is KSeF Subject1. `costs` is Subject2. NIP is 6891205697.
- A file already on disk and non-empty is skipped. That is the efficient path.
- HTTP 401 or 403 after the vault resolves means the KSeF token was revoked. Ask for a new token. Do not retry in a loop.
- Production API only: `https://api.ksef.mf.gov.pl/v2`.

## Before you finish
- [ ] every invoice or count came from the script in this run
- [ ] the reply has no token
