#!/usr/bin/env python3
"""Weekly income review: ledger numbers + kill-check + deadlines -> ~/income/reviews/<YYYY-Www>.md.

  weekly_review.py run [--week 2026-W44]     write (or refresh) the review file and print the summary
  weekly_review.py show [--week 2026-W44]    print an existing review file
The file has the numbers filled in; the sections under "## Decisions" are for the agent and the user to fill.
"""
import argparse, datetime, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import income, ledger  # noqa: E402

REVIEWS = income.INCOME / "reviews"


def week_bounds(week):
    if week:
        y, w = map(int, re.fullmatch(r"(\d{4})-W(\d{1,2})", week).groups())
        end = datetime.date.fromisocalendar(y, w, 7)
    else:
        t = income.today()
        y, w, _ = t.isocalendar()
        end = t
    return f"{y}-W{w:02d}", end


def deadlines(end, days=21):
    out = []
    for f in sorted((income.INCOME / "claims").glob("*/claim.json")):
        c = json.loads(f.read_text())
        if c.get("status") in ("paid", "refused"):
            continue
        d = c.get("answer_due") if c.get("status") == "sent" else c.get("limitation")
        what = "airline/shop answer due" if c.get("status") == "sent" else "claim limitation"
        if d and d[:4].isdigit() and (datetime.date.fromisoformat(d) - end).days <= max(days, 60):
            out.append((d, f"claim {c['id']}: {what}"))
    for slug, p in income.load_json(income.INCOME / "bank-promos" / "checklists.json", {}).items():
        if p.get("status") != "open":
            continue
        for n, it in enumerate(p["items"], 1):
            if not it["done"] and (datetime.date.fromisoformat(it["due"]) - end).days <= days:
                prog = f" ({it.get('count', 0)}/{it['target']})" if it.get("target") else ""
                out.append((it["due"], f"bank promo {slug[:40]} #{n}: {it['text']}{prog}"))
    for r in income.load_json(income.INCOME / "bailiff" / "shortlist-latest.json", [])[:5]:
        d = (r.get("deposit_by") or "")[:10]
        if d[:4].isdigit() and 0 <= (datetime.date.fromisoformat(d) - end).days <= days:
            out.append((d, f"bailiff {r['id']}: deposit {r['deposit']:.0f} PLN by {d} ({r['title'][:40]})"))
    return sorted(out)


def run(week):
    wk, end = week_bounds(week)
    s28 = ledger.summarize(end - datetime.timedelta(days=27), end)
    s7 = ledger.summarize(end - datetime.timedelta(days=6), end)
    kc = ledger.kill_check()
    rows28 = [r for r in ledger.rows(start=end - datetime.timedelta(days=27), end=end) if r["status"] != "skipped"]
    heavy = sorted(rows28, key=lambda r: -r["hours_human"])[:3]
    dl = deadlines(end)
    md = [f"# Income review {wk} (week ending {end})", "",
          "## Net per hour, last 4 weeks (PLN)", "", "| stream | attempts | wins | revenue | cost | net | hours | PLN/h | this week net |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in sorted(s28.items(), key=lambda kv: -(kv[1]["pln_h"] or -1e9)):
        md.append(f"| {k} | {v['n']} | {v['wins']} | {v['revenue']:.0f} | {v['cost']:.0f} | {v['net']:.0f} | {v['hours']:.1f} | "
                  f"{v['pln_h'] if v['pln_h'] is not None else '-'} | {s7.get(k, {}).get('net', 0):.0f} |")
    md += ["", "## Kill-check", ""] + [f"- **{r['verdict'].upper()}** {r['stream']}: {r['reason']}" for r in kc]
    md += [f"- Generic rules: {ledger.GENERIC}", "", "## Attempts that ate the most of my time (4 weeks)", ""]
    md += [f"- {r['hours_human']:.1f} h - {r['stream']} - {r['item'][:70]} ({r['status']})" for r in heavy] or ["- none logged"]
    md += ["", "## Deadlines in the next 3 weeks", ""]
    md += [f"- {d}: {t}" for d, t in dl] or ["- none"]
    q = ledger.quarter_revenue()
    if q:
        md += ["", f"Bailiff resale revenue this quarter: {q:.0f} of {ledger.QUARTER_LIMIT_PLN} PLN (unregistered activity, 03 §1.1)."]
    md += ["", "## Decisions", "", "- Move hours toward:", "- Stop / pause:", "- Win rate vs what I expected:",
           "- One change for next week:", ""]
    f = REVIEWS / f"{wk}.md"
    old = f.read_text() if f.exists() else ""
    if "## Decisions" in old:                     # keep what was already written in Decisions
        md = "\n".join(md).split("## Decisions")[0] + "## Decisions" + old.split("## Decisions", 1)[1]
    else:
        md = "\n".join(md)
    income.write(f, md)
    tot = sum(v["net"] for v in s28.values())
    print(f"Week {wk}: net last 4 weeks {tot:.0f} PLN across {len(s28)} stream(s)")
    for r in kc:
        print(f"  {r['verdict'].upper():<7}{r['stream']:<12}{r['reason'][:90]}")
    for d, t in dl[:6]:
        print(f"  due {d}: {t[:90]}")
    bad = [r for r in kc if r["verdict"] in ("kill", "pause")]
    print(f"Review: {f}")
    print(f"{'WARN' if bad else 'OK'} review written; {len(bad)} stream(s) to kill/pause, {len(dl)} deadline(s)")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0 if a else 2)
    p = argparse.ArgumentParser(prog="weekly_review.py", description=__doc__.split("\n\n")[0])
    sp = p.add_subparsers(dest="cmd", required=True)
    for n in ("run", "show"):
        sp.add_parser(n).add_argument("--week")
    x = p.parse_args()
    if x.cmd == "run":
        run(x.week)
    else:
        wk, _ = week_bounds(x.week)
        f = REVIEWS / f"{wk}.md"
        print(f.read_text() if f.exists() else f"ERROR no review for {wk}. Run: weekly_review.py run")


if __name__ == "__main__":
    main()
