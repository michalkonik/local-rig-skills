---
name: find-in-dark-web
description: Use when the user wants public onion services searched anonymously through the local Tor proxy (DuckDuckGo onion, Ahmia) for privacy or security research - legitimate content only. Not for the normal web - use /find-in-internet. Input - the search query.
---
# /find-in-dark-web
**Goal:** relevant public .onion results for a legitimate research query. **Input:** a search query.
**Output:** a short list of results in chat.
`S=~/Desktop/github_repos/local-rig-skills/skills/find-in-dark-web/scripts`
(the two scripts are symlinks to `~/Desktop/github_repos/local-rig-tools/tor-search/` - that repo is the source)

## Rules
1. Legitimate privacy and security research only: news sites' onion mirrors, privacy tools, public research,
   OSINT on public pages. If a request heads towards illegal content (abuse material, weapons, drug markets,
   stolen data, malware for use), refuse that part and do not search for, open, download or describe it.
2. Read pages only: never log in anywhere, never enter personal data, never download executables.
3. Every request goes through Tor (`tor@default`, SOCKS5 `127.0.0.1:9050`), using the commands below.

## Steps
1. Search DuckDuckGo's official onion endpoint: `python3 $S/find_in_dark_web.py "<query>" --count 8`
2. Search Ahmia (onion index that filters abuse material): `python3 $S/ahmia_query.py "<query>" --count 8`
3. Open a result if needed:
   `curl -s --socks5-hostname 127.0.0.1:9050 --max-time 60 <url> | head -c 100000`
4. Reply with the template below.

## Reply
```
Query: <query> (via Tor)
1. <title> - <.onion URL> - <one line: what it is>
...
Not shown: <anything refused under rule 1, or "nothing">
```

## Gotchas
- Tor circuits take 10-60 s; retry once when slow or failing.
- Daemon check: `systemctl status tor@default`.

## Before you finish
- [ ] Every result is legitimate content (rule 1).
- [ ] Nothing was logged into, submitted or downloaded as an executable.
