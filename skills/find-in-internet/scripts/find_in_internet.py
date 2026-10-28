#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill: /find-in-internet
Search the surface (clearnet) web over the DIRECT internet connection.

Usage:
    find_in_internet.py "<query>" [--count N]

Backends (tried in order until one yields results):
  1. Bing RSS (https://www.bing.com/search?q=<q>&format=rss) — sensitive to
     IP reputation; may return low-relevance results for bot/datacenter IPs.
  2. DuckDuckGo HTML (https://html.duckduckgo.com/html/?q=<q>) — retries with
     cookie+referer; can be served a captcha/challenge page (IP throttling).

The agent should sanity-check results before relying on them, because public
search engines throttle and may deprioritize automated queries.
"""

import sys
import os
import time
import re
import html as htmllib
import urllib.parse
import urllib.request
import random

UA_BASE = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def http_get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": random.choice(UA_BASE),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Referer": "https://duckduckgo.com/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        # try to decode utf-8, fall back to latin-1
        return raw.decode("utf-8", errors="replace")


def htmldec(s: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def bing_rss(query: str) -> list[dict]:
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(query) + "&format=rss"
    xml = http_get(url)
    out = []
    items = re.findall(r"<item>(.*?)</item>", xml, re.S)
    for it in items:
        title = htmldec(re.search(r"<title>(.*?)</title>", it, re.S).group(1))
        link = htmldec(re.search(r"<link>(.*?)</link>", it, re.S).group(1))
        desc = htmldec(re.search(r"<description>(.*?)</description>", it, re.S).group(1))
        if title and link:
            out.append({"title": title, "url": link, "snippet": desc[:200], "source": "bing"})
    return out


def ddg_html(query: str) -> list[dict]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    for attempt in range(3):
        # rotate the cookie so DDG may serve a real page instead of a challenge
        req = urllib.request.Request(url, headers={
            "User-Agent": random.choice(UA_BASE),
            "Cookie": "d=%d" % random.randint(1, 32),
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="replace")
        if "result__a" not in html:
            time.sleep(2)   # back off, challenge may be transient
            continue
        out = []
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
            raw = htmllib.unescape(m.group(1))
            # unwrap DDG redirect link if present
            m2 = re.search(r"uddg=([^&]+)", raw)
            url2 = urllib.parse.unquote(m2.group(1)) if m2 else raw
            title = htmldec(m.group(2))
            out.append({"title": title, "url": url2, "snippet": "", "source": "ddg"})
        return out
    return []


def main(argv):
    args = list(argv)
    count = 5
    if "--count" in args:
        i = args.index("--count")
        count = int(args[i + 1]); del args[i:i + 2]
    query = " ".join(args).strip()
    if not query:
        print("usage: find_in_internet.py \"<query>\" [--count N]")
        return 2

    results = []
    src_used = "..."
    # try Bing RSS first
    try:
        results = bing_rss(query)
        src_used = "bing"
    except Exception as e:
        print(f"[bing error: {e}]")
    if not results:
        try:
            results = ddg_html(query)
            src_used = "ddg"
        except Exception as e:
            print(f"[ddg error: {e}]")

    if not results:
        print(f"no results (search engines throttled this IP) for: {query}")
        print("The agent should fetch candidate URLs directly, or retry later.")
        return 1

    out = results[:count]
    print(f"TOP {len(out)} RESULTS for: {query}  (source: {src_used})\n")
    for i, r in enumerate(out, 1):
        print(f"{i}. {r['title']}")
        print(f"   {r['url']}")
        if r["snippet"]:
            print(f"   {r['snippet'][:180]}")
        print()
    print("Note: verify each link; automated search results from public engines")
    print("may be incomplete or of mixed relevance.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
