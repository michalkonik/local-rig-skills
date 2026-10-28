#!/usr/bin/env python3
"""Polish bank promotions: fetch the public list (kontomaniak.pl), diff vs last run, keep a dated checklist per promo.

  promos.py fetch [--business] [--file saved.html]   list + detail pages -> ~/income/bank-promos/ (cached 6 h)
  promos.py show SLUG                                the stored terms summary of one promo
  promos.py start SLUG                               you opened the account: checklist + ledger attempt
  promos.py check add SLUG --text "5 card payments" --due 2026-12-31 [--target 5]
  promos.py check progress SLUG N --count 3 | check done SLUG N
  promos.py due [--days 21]                          open conditions by date, overdue first
  promos.py outcome SLUG paid|lost|refused [--amount 700]
Excluded banks (you have/had an account there): one name per line in ~/income/bank-promos/excluded-banks.txt
"""
import argparse, datetime, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import income, ledger  # noqa: E402

BASE = "https://www.kontomaniak.pl"
LIST = BASE + "/promocje-bankowe"
DIR = income.INCOME / "bank-promos"
CHECK = DIR / "checklists.json"
KIDS = re.compile(r"dla dziecka|dla dzieci|kids", re.I)
BUSINESS = re.compile(r"firm|biznes|business|sp[oó]łk|przedsi", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("stycznia lutego marca kwietnia maja czerwca lipca sierpnia września "
                                          "października listopada grudnia".split())}


def parse_list(html):
    out = []
    for c in re.findall(r'<div class="article-list-item.*?</h3>', html, re.S):
        h = re.search(r'href="(/promocje/([^/"]+)/([^"]+))"', c)
        if not h:
            continue
        badge = re.search(r'badge-promo"><p>(.*?)</p>', c, re.S)
        cd = re.search(r'counting-down-badge">.*?</svg>\s*(.*?)\s*</div>', c, re.S)
        title = income.html_text(re.search(r'<h3 class="title">(.*?)</h3>', c, re.S).group(1))
        bonus_txt = income.html_text(badge.group(1)) if badge else ""
        m = re.search(r"(\d[\d  ]*)\s*zł", bonus_txt) or re.search(r"(\d[\d  ]*)\s*zł", title)
        out.append({"slug": h.group(3), "bank": h.group(2), "url": BASE + h.group(1), "title": title,
                    "bonus_pln": int(re.sub(r"\D", "", m.group(1))) if m else 0, "badge": bonus_txt,
                    "active": bool(cd), "ends_hint": cd.group(1).strip() if cd else "ended",
                    "business": bool(BUSINESS.search(title + " " + h.group(3)))})
    return out


def dates_in(text):
    """All dates in the text as ISO strings (dd.mm.yyyy and '30 listopada 2026')."""
    found = set()
    for d, m, y in re.findall(r"\b(\d{1,2})\.(\d{1,2})\.(20\d\d)\b", text):
        found.add(f"{y}-{int(m):02d}-{int(d):02d}")
    for d, mon, y in re.findall(r"\b(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(20\d\d)", text):
        if mon in MONTHS:
            found.add(f"{y}-{MONTHS[mon]:02d}-{int(d):02d}")
    return sorted(found)


def parse_detail(html):
    t = income.html_text(html)
    pill = {}
    for key, label in (("end", "Data zakończenia"), ("gain", "Co można zyskać?"), ("who", "Kto może skorzystać?"),
                       ("conditions", "Warunki promocji")):
        m = re.search(re.escape(label) + r"\s*(.+)", t)
        if m:
            pill[key] = m.group(1).strip()[:400]
    end = re.search(r"(\d{2})\.(\d{2})\.(20\d\d)", pill.get("end", ""))
    pill["end_date"] = f"{end.group(3)}-{end.group(2)}-{end.group(1)}" if end else None
    body = t.find("Warunki promocji\n", t.find("Spis treści"))
    sect = t[body:body + 3500] if body > 0 else ""
    cut = re.search(r"\n(Dodatkowa premia|Wyższe oprocentowanie|O Koncie|Podsumowanie|Cechy promocji)", sect)
    pill["terms"] = sect[:cut.start()] if cut else sect
    pill["dates"] = dates_in(pill["terms"] + " " + pill.get("end", ""))
    return pill


def excluded():
    f = DIR / "excluded-banks.txt"
    if not f.exists():
        income.write(f, "# Banks where you have or recently had a personal account (one per line, e.g. mbank, pko-bp).\n")
    return {income.slug(l) for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")}


def fetch(x):
    html = pathlib.Path(x.file).read_text() if x.file else income.fetch(LIST)
    promos = parse_list(html)
    if not promos:
        raise SystemExit(f"ERROR no promotions parsed from {x.file or LIST} - the page layout changed; save the page "
                         "in a browser and run: promos.py fetch --file saved.html, then report the change")
    excl = excluded()
    active = [p for p in promos if p["active"] and (x.business or not p["business"])]
    for p in active:
        try:
            p.update(parse_detail(income.fetch(p["url"])))
        except income.Blocked as e:
            p["error"] = str(e)
        p["excluded"] = income.slug(p["bank"]) in excl or any(e in income.slug(p["title"]) for e in excl)
        income.write(DIR / "offers" / f"{p['slug']}.md",
                     f"# {p['title']}\n{p['url']}\nBank: {p['bank']}  Bonus: {p['bonus_pln']} PLN  Ends: {p.get('end_date')}\n\n"
                     f"Who: {p.get('who', '?')}\nGain: {p.get('gain', '?')}\nConditions (summary): {p.get('conditions', '?')}\n"
                     f"Dates found: {', '.join(p.get('dates', []))}\n\n<terms source=\"kontomaniak.pl, third-party summary - "
                     f"the bank's regulamin is binding\">\n{p.get('terms', '')}\n</terms>\n")
    snaps = sorted(f for f in (DIR / "snapshots").glob("*.json") if f.stem < str(income.today()))
    prev = {p["slug"]: p for p in income.load_json(snaps[-1], [])} if snaps else {}
    now = {p["slug"]: p for p in active}
    new, ended = [s for s in now if s not in prev], [s for s in prev if s not in now]
    income.save_json(DIR / "snapshots" / f"{income.today()}.json", active)
    eligible = [p for p in active if not p["excluded"] and not p["business"] and not KIDS.search(p["title"])]
    income.save_json(DIR / "state.json", {"fetched": str(income.today()), "eligible_bonus_pln": sum(p["bonus_pln"] for p in eligible),
                                          "new": new, "ended": ended})
    for p in sorted(active, key=lambda p: -p["bonus_pln"]):
        flag = "NEW " if p["slug"] in new else "    "
        flag += "excl" if p["excluded"] else ("biz " if p["business"] else "    ")
        print(f"{flag} {p['bonus_pln']:>6} PLN  ends {p.get('end_date') or p['ends_hint']:<12} {p['bank']:<18} {p['slug']}")
    for s in ended:
        print(f"ENDED        {prev[s]['bank']:<18} {s}")
    print(f"Open offers for you: {sum(p['bonus_pln'] for p in eligible)} PLN in {len(eligible)} promo(s). Files: {DIR}/offers/")
    print(f"OK {len(active)} active, {len(new)} new, {len(ended)} ended since the last run")


def checklists():
    return income.load_json(CHECK, {})


def save(c):
    income.save_json(CHECK, c)
    lines = ["# Bank promo checklists", ""]
    for slug, p in c.items():
        lines += [f"## {p['title']} ({p['status']})", p["url"], ""]
        for i, it in enumerate(p["items"], 1):
            box = "x" if it["done"] else " "
            prog = f" ({it.get('count', 0)}/{it['target']})" if it.get("target") else ""
            lines.append(f"- [{box}] {i}. {it['text']}{prog} - by {it['due']}")
        lines.append("")
    income.write(DIR / "checklists.md", "\n".join(lines))


def find_promo(slug):
    for f in sorted((DIR / "snapshots").glob("*.json"), reverse=True):
        for p in income.load_json(f, []):
            if p["slug"] == slug or p["slug"].startswith(slug):
                return p
    raise SystemExit(f"ERROR promo '{slug}' not in any snapshot. Run: promos.py fetch, then use a slug it prints")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0 if a else 2)
    p = argparse.ArgumentParser(prog="promos.py", description=__doc__.split("\n\n")[0])
    sp = p.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fetch"); f.add_argument("--business", action="store_true"); f.add_argument("--file")
    sh = sp.add_parser("show"); sh.add_argument("slug")
    st = sp.add_parser("start"); st.add_argument("slug")
    ck = sp.add_parser("check"); ck.add_argument("action", choices=("add", "progress", "done"))
    ck.add_argument("slug"); ck.add_argument("n", nargs="?", type=int); ck.add_argument("--text"); ck.add_argument("--due")
    ck.add_argument("--target", type=int); ck.add_argument("--count", type=int)
    du = sp.add_parser("due"); du.add_argument("--days", type=int, default=21)
    oc = sp.add_parser("outcome"); oc.add_argument("slug"); oc.add_argument("status", choices=("paid", "lost", "refused"))
    oc.add_argument("--amount", type=float, default=0.0)
    x = p.parse_args()
    c = checklists()

    if x.cmd == "fetch":
        try:
            fetch(x)
        except income.Blocked as e:
            print(f"ERROR {e}. Save {LIST} in a browser (Ctrl+S) and run: promos.py fetch --file <saved.html>")
            sys.exit(3)
    elif x.cmd == "show":
        pr = find_promo(x.slug)
        print((DIR / "offers" / f"{pr['slug']}.md").read_text()[:3500])
    elif x.cmd == "start":
        pr = find_promo(x.slug)
        if pr["slug"] in c:
            print(f"OK already tracked: {pr['slug']}"); return
        lid = ledger.add_attempt("bank-promos", pr["url"], status="open", note=f"bonus {pr['bonus_pln']} PLN, ends {pr.get('end_date')}")
        c[pr["slug"]] = {"title": pr["title"], "url": pr["url"], "bank": pr["bank"], "bonus_pln": pr["bonus_pln"],
                         "status": "open", "ledger_id": lid, "items": []}
        save(c)
        print(f"Dates in the terms: {', '.join(pr.get('dates', [])) or 'none found - read the regulamin'}")
        print(f"OK tracking {pr['slug']} (ledger {lid}). Now add each condition: promos.py check add {pr['slug']} --text ... --due ...")
    elif x.cmd == "check":
        if x.slug not in c:
            raise SystemExit(f"ERROR {x.slug} not tracked. Run: promos.py start {x.slug}")
        items = c[x.slug]["items"]
        if x.action == "add":
            if not (x.text and x.due):
                raise SystemExit("ERROR check add needs --text and --due YYYY-MM-DD")
            datetime.date.fromisoformat(x.due)
            items.append({"text": x.text, "due": x.due, "target": x.target, "count": 0, "done": False})
            items.sort(key=lambda i: i["due"])
        else:
            if not x.n or not 1 <= x.n <= len(items):
                raise SystemExit(f"ERROR give the condition number 1..{len(items)} (see ~/income/bank-promos/checklists.md)")
            it = items[x.n - 1]
            if x.action == "progress":
                it["count"] = x.count or 0
                it["done"] = bool(it.get("target")) and it["count"] >= it["target"]
            else:
                it["done"] = True
        save(c)
        print(f"OK {x.slug}: {sum(i['done'] for i in items)}/{len(items)} conditions met. File: {DIR}/checklists.md")
    elif x.cmd == "due":
        t, rows = income.today(), []
        for slug, pr in c.items():
            if pr["status"] != "open":
                continue
            for n, it in enumerate(pr["items"], 1):
                days = (datetime.date.fromisoformat(it["due"]) - t).days
                if not it["done"] and days <= x.days:
                    rows.append((days, slug, n, it))
        for days, slug, n, it in sorted(rows, key=lambda r: r[0]):
            prog = f" {it.get('count', 0)}/{it['target']}" if it.get("target") else ""
            print(f"{'OVERDUE' if days < 0 else f'in {days:>2} d'}  {it['due']}  {slug[:40]} #{n}: {it['text']}{prog}")
        late = sum(1 for r in rows if r[0] < 0)
        print(f"{'WARN' if late else 'OK'} {len(rows)} open condition(s) due within {x.days} days, {late} overdue")
    elif x.cmd == "outcome":
        if x.slug not in c:
            raise SystemExit(f"ERROR {x.slug} not tracked")
        pr = c[x.slug]
        pr["status"] = x.status
        ledger.update(pr["ledger_id"], status=x.status, revenue=x.amount or None)
        save(c)
        print(f"OK {x.slug} -> {x.status}" + (f", {x.amount} PLN logged" if x.amount else ""))


if __name__ == "__main__":
    main()
