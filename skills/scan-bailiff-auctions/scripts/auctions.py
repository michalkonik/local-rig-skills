#!/usr/bin/env python3
"""Polish bailiff e-auctions (licytacje.komornik.pl): public listings -> discount vs appraisal, deposit, dates, shortlist.

  auctions.py scan [--category CARS,TOOLS|movable|real-estate] [--province mazowieckie] [--max-price 4000]
                   [--max-estimate 5000] [--pages 3] [--top 15] [--file saved.html]
  auctions.py categories            valid --category and --province values
  auctions.py record ID shortlisted|bid|bought|sold|lost [--cost 3000] [--revenue 4200] [--hours 3]
Reads only the public search pages (robots.txt allows them), <= 1 request / 1.2 s, cached 6 h. Never logs in or bids.
Output: ~/income/bailiff/shortlist-<date>.md and shortlist-latest.json. Rules and sources: ../reference.md
"""
import argparse, datetime, json, pathlib, re, sys, urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import income, ledger  # noqa: E402

BASE = "https://licytacje.komornik.pl"
DIR = income.INCOME / "bailiff"
PROVINCES = ("dolnośląskie kujawsko-pomorskie lubelskie lubuskie łódzkie małopolskie mazowieckie opolskie podkarpackie "
             "podlaskie pomorskie śląskie świętokrzyskie warmińsko-mazurskie wielkopolskie zachodniopomorskie").split()
MOVABLE = ("ART JEWELRY INDUSTRIAL_MACHINES AGRICULTURAL_MACHINERY INDUSTRIAL_MATERIALS FURNITURE MOTORCYCLES CLOTHING "
           "OTHER_MOVABLE TRAILERS TRUCKS CARS HOUSEHOLD COMPUTER TV_EQUIPMENT RAW_MATERIALS BOATS").split()
REAL_ESTATE = "HOUSES GARAGES LAND OTHER COMMERCIAL_PREMISESISES WAREHOUSES_AND_HALLS APARTMENTS SEA_VESSELS".split()
LIVE = ("CREATED", "IN_PROGRESS", "PUBLISHED", "ACTIVE")
PAGE = 100


def decode_nuxt(html):
    """Decode Nuxt's __NUXT_DATA__ (devalue format: a flat array where containers hold indexes)."""
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {}
    arr, memo = json.loads(m.group(1)), {}

    def h(i):
        if not isinstance(i, int) or i < 0:
            return None
        if i in memo:
            return memo[i]
        v = arr[i]
        if isinstance(v, list):
            tag = v[0] if v and isinstance(v[0], str) else None
            if tag in ("ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"):
                r = h(v[1]) if len(v) > 1 else None
            elif tag in ("Date", "BigInt", "RegExp"):
                r = v[1]
            elif tag == "Set":
                r = [h(k) for k in v[1:]]
            elif tag == "Map":
                r = {str(h(v[k])): h(v[k + 1]) for k in range(1, len(v), 2)}
            elif tag == "null":
                r = {}
            else:
                memo[i] = r = []
                r.extend(h(k) for k in v)
                return r
        elif isinstance(v, dict):
            memo[i] = r = {}
            for k, val in v.items():
                r[k] = h(val) if k != "mainPhoto" else None     # base64 photos: skip
            return r
        else:
            r = v
        memo[i] = r
        return r
    return h(0) or {}


def items_from(html):
    d = (decode_nuxt(html).get("data") or {}).get("search-items") or {}
    links = dict(re.findall(r'href="/licytacje/(\d+)/([^"]+)"', html))
    for it in d.get("items") or []:
        it["url"] = f"{BASE}/licytacje/{it['id']}/{links.get(str(it['id']), 'x')}"
    return d.get("items") or [], d.get("count") or 0


def term_of(it):
    """Which auction term the opening price implies (art. 867 § 2 KPC movables, art. 965 / 983 § 1 KPC real estate)."""
    est, opening = it.get("estimate") or 0, it.get("openingValue") or 0
    if not est or not opening:
        return "?", None
    r = opening / est
    if it.get("mainCategory") == "REAL_ESTATE":
        known = ((0.75, "1st term 3/4 (art. 965 KPC)"), (2 / 3, "2nd term 2/3 (art. 983 § 1 KPC)"))
    else:
        known = ((0.75, "1st term 3/4 (art. 867 § 2 KPC)"), (0.5, "2nd term 1/2 (art. 867 § 2 KPC)"))
    for k, label in known:
        if abs(r - k) < 0.01:
            return label, r
    return f"other ratio {r:.2f} - read the notice", r


def deposit(it):
    """Rekojmia: 1/10 of the appraisal; none for movables appraised under 5,000 PLN (art. 867(1) § 1, art. 962 § 1 KPC)."""
    est = it.get("estimate") or 0
    if it.get("mainCategory") != "REAL_ESTATE" and est < 5000:
        return 0.0
    return round(est / 10, 2)


def deposit_by(it):
    if not deposit(it):
        return "-"
    if it.get("marginDueDate"):
        return it["marginDueDate"][:10]
    start = it.get("startAuctionAt")
    if not start or not it.get("eauction"):
        return "see notice"
    d, n = datetime.date.fromisoformat(start[:10]), 0
    while n < 2:                                   # 2 working days before the start (art. 879(5) KPC, per the course)
        d -= datetime.timedelta(days=1)
        n += d.weekday() < 5
    return f"{d} (est.)"


def scan(x):
    cats = [c.strip().upper().replace("-", "_") for c in (x.category or "movable").split(",")]
    if cats == ["MOVABLE"]:
        main, subs = "MOVABLE", [None]
    elif cats == ["REAL_ESTATE"]:
        main, subs = "REAL_ESTATE", [None]
    else:
        bad = [c for c in cats if c not in MOVABLE + REAL_ESTATE]
        if bad:
            raise SystemExit(f"ERROR unknown category {bad}. Run: auctions.py categories")
        main, subs = ("REAL_ESTATE" if cats[0] in REAL_ESTATE else "MOVABLE"), cats
    if x.province and x.province not in PROVINCES:
        raise SystemExit(f"ERROR unknown province '{x.province}'. Valid: {', '.join(PROVINCES)}")
    found = []
    if x.file:
        found = items_from(pathlib.Path(x.file).read_text())[0]
    for sub in ([] if x.file else subs):
        for page in range(x.pages):
            q = {"mainCategory": main, "limit": PAGE, "offset": page * PAGE}
            if sub:
                q["subCategory"] = sub
            if x.province:
                q["province"] = x.province
            url = f"{BASE}/wyszukiwarka-licytacji?" + urllib.parse.urlencode(q)
            items, count = items_from(income.fetch(url))
            found += items
            print(f"{sub or main} page {page + 1}: {len(items)} of {count}", file=sys.stderr)
            if (page + 1) * PAGE >= count or not items:
                break
    if not found:
        raise SystemExit("ERROR no listings parsed - the page layout may have changed. Save the search page in a browser "
                         "and run: auctions.py scan --file saved.html")
    seen = income.load_json(DIR / "seen.json", {})
    rows, t = [], str(income.today())
    for it in {i["id"]: i for i in found}.values():
        if it.get("status") not in LIVE or (it.get("endAuctionAt") or "9")[:10] < t:
            continue
        if x.max_price and (it.get("openingValue") or 0) > x.max_price:
            continue
        if x.max_estimate and (it.get("estimate") or 0) > x.max_estimate:
            continue
        if it.get("joinable") is False:
            continue
        dby = deposit_by(it)
        if dby[:4].isdigit() and dby[:10] < t:          # deposit window already closed
            continue
        term, ratio = term_of(it)
        rows.append({"id": it["id"], "title": it.get("title", ""), "sub": it.get("subCategory"), "estimate": it.get("estimate"),
                     "opening": it.get("openingValue"), "discount": round(1 - ratio, 3) if ratio else 0, "term": term,
                     "deposit": deposit(it), "deposit_by": dby, "start": (it.get("startAuctionAt") or "")[:16],
                     "end": (it.get("endAuctionAt") or "")[:16], "eauction": it.get("eauction"),
                     "place": f"{(it.get('address') or {}).get('city', '')}, {it.get('province', '')}",
                     "url": it["url"], "new": str(it["id"]) not in seen})
        seen.setdefault(str(it["id"]), t)
    income.save_json(DIR / "seen.json", seen)
    rows.sort(key=lambda r: (-r["discount"], r["start"]))
    short = rows[:x.top]
    md = [f"# Bailiff auction shortlist {t}", f"Filters: {main} {','.join(s for s in subs if s) or ''} {x.province or 'all PL'} "
          f"max price {x.max_price or '-'} max appraisal {x.max_estimate or '-'}", "",
          "| # | new | item | appraisal | opening | discount | term | deposit | deposit by | auction | place |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in enumerate(short, 1):
        md.append(f"| {n} | {'yes' if r['new'] else ''} | [{r['title'][:60]}]({r['url']}) | {r['estimate']} | {r['opening']} | "
                  f"{r['discount']:.0%} | {r['term']} | {r['deposit']:.0f} | {r['deposit_by']} | {r['start']} -> {r['end']} | {r['place']} |")
    md += ["", "Resale price, transport, defects and legal traps: check by hand before any bid. Bidding needs your PESEL "
           "and your own account on the portal; you bid yourself."]
    income.write(DIR / f"shortlist-{t}.md", "\n".join(md) + "\n")
    income.save_json(DIR / "shortlist-latest.json", short)
    for n, r in enumerate(short[:10], 1):
        print(f"{n:>2} {r['discount']:>4.0%} {r['opening']:>9} / {r['estimate']:<9} dep {r['deposit']:>7.0f} by {r['deposit_by']:<16} "
              f"{r['start'][:10]} {r['title'][:45]}")
    print(f"Shortlist: {DIR}/shortlist-{t}.md")
    print(f"OK {len(rows)} live listing(s) after filters, {sum(r['new'] for r in rows)} new, top {len(short)} written")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0 if a else 2)
    p = argparse.ArgumentParser(prog="auctions.py", description=__doc__.split("\n\n")[0])
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("scan")
    s.add_argument("--category"); s.add_argument("--province"); s.add_argument("--max-price", type=float)
    s.add_argument("--max-estimate", type=float, default=5000.0); s.add_argument("--pages", type=int, default=3)
    s.add_argument("--top", type=int, default=15); s.add_argument("--file")
    sp.add_parser("categories")
    r = sp.add_parser("record"); r.add_argument("id"); r.add_argument("status", choices=ledger.STATUSES["bailiff"])
    r.add_argument("--cost", type=float); r.add_argument("--revenue", type=float); r.add_argument("--hours", type=float)
    x = p.parse_args()
    if x.cmd == "categories":
        print("movable: " + " ".join(MOVABLE)); print("real-estate: " + " ".join(REAL_ESTATE))
        print("provinces: " + " ".join(PROVINCES)); print("OK")
    elif x.cmd == "scan":
        try:
            scan(x)
        except income.Blocked as e:
            print(f"ERROR {e}. Open the search in a browser, save it (Ctrl+S) and run: auctions.py scan --file saved.html")
            sys.exit(3)
    elif x.cmd == "record":
        book = income.load_json(DIR / "ledger-ids.json", {})
        if x.id in book:
            res = ledger.update(book[x.id], status=x.status, cost=x.cost, revenue=x.revenue, hours=x.hours)
        else:
            item = next((r for r in income.load_json(DIR / "shortlist-latest.json", []) if str(r["id"]) == x.id), None)
            url = item["url"] if item else f"{BASE}/licytacje/{x.id}/x"
            book[x.id] = ledger.add_attempt("bailiff", url, hours=x.hours or 0, cost=x.cost or 0, revenue=x.revenue or 0,
                                            status=x.status, note=item["title"][:80] if item else "")
            income.save_json(DIR / "ledger-ids.json", book)
            res = {"id": book[x.id], "status": x.status}
        print(f"OK auction {x.id} -> {res['status']} (ledger attempt {res['id']})")


if __name__ == "__main__":
    main()
