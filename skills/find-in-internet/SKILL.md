---
name: find-in-internet
description: Use when the user wants something looked up on the public web ("search the web", "find out", "what is the latest") - several searches, reads the best pages, cross-checks, answers with cited URLs and dates. Not for onion sites - use /find-in-dark-web. Input - the question or topic.
---
# /find-in-internet
**Goal:** a direct answer backed by sources. **Input:** a question or topic. **Output:** the answer in chat with
every source as URL + publication/update date.

## Rules
1. Search with the web tool of your UI: Open WebUI `web_search` / `fetch_url`; llama.cpp UI `rig-web_web_search` /
   `rig-web_fetch_url`. Without tools use the script in step 2.
2. Prefer primary sources: official docs, release notes, papers, the project's GitHub, the vendor's model card.
3. Cite every source as URL + date and say what you could not verify.

## Steps
1. When "latest/current" is asked, check today's date: `date`.
2. Run 2-4 different queries (synonyms, the English term, add the year for recent topics, `site:` for official
   docs/GitHub). Fallback without tools:
   `python3 ~/Desktop/github_repos/local-rig-skills/skills/find-in-internet/scripts/find_in_internet.py "<query>" --count 8`
3. Read the 2-5 most relevant pages with `fetch_url` / `rig-web_fetch_url` (or `curl -sL URL | head -c 200000`).
4. Cross-check facts that matter (numbers, versions, dates) in a second source; note disagreements.
5. Reply with the template below.

## Reply
```
<direct answer, 1-3 sentences>
Evidence:
- <fact> - <URL> (<date>)
Sources disagree on: <point, or "nothing">
Not verified: <what, or "nothing">
```

## Gotchas
- The fallback script tries Bing RSS, then DuckDuckGo HTML. Both throttle automated queries and may return
  low-relevance results or a captcha page; then fetch known URLs directly.

## Before you finish
- [ ] Every fact in the answer has a URL + date.
- [ ] For "latest/current" questions the answer is checked against today's date.
- [ ] Anything unverified is labelled.
