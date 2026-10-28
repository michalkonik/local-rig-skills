#!/usr/bin/env python3
"""Income ledger: one SQLite row per attempt, so every stream is judged on numbers (course 02 section 4).

  ledger.py add-attempt --stream S --item ITEM [--date D] [--hours H] [--cost C] [--revenue R] [--currency EUR]
                        [--status ST] [--note N]
  ledger.py update ID [--status ST] [--hours H] [--cost C] [--revenue R] [--currency USD] [--note N]
  ledger.py list [--stream S] [--status ST] [--limit 30]
  ledger.py summary [--month 2026-10 | --days 28]
  ledger.py kill-check                      keep / kill / extend / pause per stream, with the reason
  ledger.py stream NAME --status active|paused|killed

Amounts are stored in PLN. --currency converts at the NBP rate of the last business day before --date (D-1 rule).
Examples:  ledger.py add-attempt --stream claims --item "LO123 2026-08-14 WAW-BCN" --status sent --hours 0.3
           ledger.py update 7 --status paid --revenue 250 --currency EUR
"""
import argparse, datetime, json, pathlib, sqlite3, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import income  # noqa: E402

STREAMS = ("claims", "freelance", "bank-promos", "bailiff")
STATUSES = {
    "claims": ("drafted", "sent", "escalated", "paid", "refused", "skipped"),
    "freelance": ("proposed", "won", "delivered", "paid", "lost", "skipped"),
    "bank-promos": ("open", "paid", "lost", "refused", "skipped"),
    "bailiff": ("shortlisted", "bid", "bought", "sold", "lost", "skipped"),
}
COMMON = ("pending", "flagged")          # flagged = ToS warning, account flag or payout refused over a rules question
WINS = ("paid", "won", "delivered", "sold")
FLOOR_USD_H = 30.0                       # course 02 section 3: my hourly floor
QUARTER_LIMIT_PLN = 10813.50             # 03 section 1.1: dzialalnosc nierejestrowana 2026, per quarter

# Kill criteria, written down before starting (01-OPPORTUNITIES.md profile of each stream; 02 section 4 for GENERIC).
KILL = {
    "claims": {"test_days": 7,
               "rule": "Nothing eligible found in the backlog after the first week -> keep only the yearly PIT check (01 §1)"},
    "freelance": {"test_days": 42, "test_attempts": 60, "min_net_usd_month": 100, "max_hours_per_job": 3,
                  "rule": "After 6 weeks and 60 proposals: net < 100 USD/month or > 3 h of my time per job -> stop (01 §2)"},
    "bank-promos": {"lost_in_row": 2, "min_open_pln": 1500,
                    "rule": "Two bonuses in a row lost/refused, or open offers for me < 1,500 PLN a year -> stop (01 §9)"},
    "bailiff": {"test_days": 61, "test_purchases": 3, "min_margin": 0.10, "stuck_days": 60,
                "rule": "After 2 months and 3 purchases: net margin < 10% or capital stuck in unsold items -> stop (01 §6)"},
}
GENERIC = ("4 weeks below the 30 USD/h floor with no upward trend -> stop; 20 attempts with zero wins -> stop or change "
           "the method; any ToS warning or account flag -> pause (02 §4)")

SCHEMA = """
CREATE TABLE IF NOT EXISTS streams (name TEXT PRIMARY KEY, started TEXT, status TEXT DEFAULT 'active');
CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, stream TEXT, date TEXT, item TEXT, hours_human REAL DEFAULT 0,
  cost REAL DEFAULT 0, revenue REAL DEFAULT 0, status TEXT, note TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS attempts_stream ON attempts(stream, date);
"""


def db():
    income.DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(income.DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _check(stream, status):
    if stream not in STREAMS:
        raise SystemExit(f"ERROR unknown stream '{stream}'. Valid: {', '.join(STREAMS)}")
    ok = STATUSES[stream] + COMMON
    if status and status not in ok:
        raise SystemExit(f"ERROR status '{status}' not valid for {stream}. Valid: {', '.join(ok)}")


def to_pln(amount, currency, day):
    if not amount or currency.upper() == "PLN":
        return amount or 0.0, ""
    rate, src = income.nbp_rate(currency, day)
    return round(amount * rate, 2), f"{amount} {currency.upper()} x {rate} ({src})"


def add_attempt(stream, item, date=None, hours=0.0, cost=0.0, revenue=0.0, status="pending", note="", currency="PLN"):
    _check(stream, status)
    day = datetime.date.fromisoformat(date) if date else income.today()
    cost, n1 = to_pln(cost, currency, day)
    revenue, n2 = to_pln(revenue, currency, day)
    note = "; ".join(x for x in (note, n1, n2) if x)
    with db() as c:
        c.execute("INSERT OR IGNORE INTO streams(name, started, status) VALUES (?,?, 'active')", (stream, str(day)))
        c.execute("UPDATE streams SET started=? WHERE name=? AND started>?", (str(day), stream, str(day)))
        cur = c.execute("INSERT INTO attempts(stream,date,item,hours_human,cost,revenue,status,note) VALUES (?,?,?,?,?,?,?,?)",
                        (stream, str(day), item, hours, cost, revenue, status, note))
        return cur.lastrowid


def update(aid, status=None, hours=None, cost=None, revenue=None, note=None, currency="PLN", date=None):
    with db() as c:
        row = c.execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone()
        if not row:
            raise SystemExit(f"ERROR attempt {aid} not found. See: ledger.py list")
        _check(row["stream"], status)
        day = datetime.date.fromisoformat(date) if date else income.today()
        sets, vals, extra = [], [], []
        for col, v in (("status", status), ("hours_human", hours)):
            if v is not None:
                sets.append(f"{col}=?"); vals.append(v)
        for col, v in (("cost", cost), ("revenue", revenue)):
            if v is not None:
                pln, n = to_pln(v, currency, day)
                sets.append(f"{col}=?"); vals.append(pln)
                if n:
                    extra.append(n)
        if note is not None or extra:
            sets.append("note=?"); vals.append("; ".join(x for x in ((note if note is not None else row["note"]), *extra) if x))
        if not sets:
            raise SystemExit("ERROR nothing to update; give --status/--hours/--cost/--revenue/--note")
        c.execute(f"UPDATE attempts SET {', '.join(sets)} WHERE id=?", (*vals, aid))
    return dict(db().execute("SELECT * FROM attempts WHERE id=?", (aid,)).fetchone())


def rows(stream=None, start=None, end=None):
    q, a = "SELECT * FROM attempts WHERE 1=1", []
    if stream:
        q += " AND stream=?"; a.append(stream)
    if start:
        q += " AND date>=?"; a.append(str(start))
    if end:
        q += " AND date<=?"; a.append(str(end))
    return [dict(r) for r in db().execute(q + " ORDER BY date, id", a)]


def summarize(start=None, end=None):
    out = {}
    for r in rows(start=start, end=end):
        s = out.setdefault(r["stream"], {"n": 0, "wins": 0, "cost": 0.0, "revenue": 0.0, "hours": 0.0})
        if r["status"] == "skipped":
            continue
        s["n"] += 1
        s["wins"] += r["status"] in WINS
        s["cost"] += r["cost"]; s["revenue"] += r["revenue"]; s["hours"] += r["hours_human"]
    for s in out.values():
        s["net"] = round(s["revenue"] - s["cost"], 2)
        s["pln_h"] = round(s["net"] / s["hours"], 1) if s["hours"] else None
    return out


def usd_pln():
    try:
        return income.nbp_rate("USD")[0], ""
    except income.Blocked:
        return 4.0, " (NBP offline: assumed 4.00 PLN/USD)"


def _verdict_stream(name, started, data, today, usd):
    k, a = KILL.get(name, {}), [r for r in data if r["status"] != "skipped"]
    age = (today - datetime.date.fromisoformat(started)).days
    if any(r["status"] == "flagged" for r in a):
        return "pause", "a ToS warning / account flag is logged - pause this platform and read the terms (02 §4)"
    if name == "claims":
        if age < k["test_days"]:
            return "extend", f"first-week backlog scan, day {age}/{k['test_days']}"
        if not any(r["status"] in ("drafted", "sent", "escalated", "paid") for r in a):
            return "kill", "nothing eligible found in the backlog -> keep only the yearly PIT check (01 §1)"
    if name == "freelance":
        props = [r for r in a if r["status"] in ("proposed", "won", "delivered", "paid", "lost")]
        jobs = [r for r in a if r["status"] in ("won", "delivered", "paid")]
        net_usd_m = sum(r["revenue"] - r["cost"] for r in a) / usd / max(age / 30.4, 1)
        h_job = sum(r["hours_human"] for r in jobs) / len(jobs) if jobs else 0
        if age < k["test_days"] or len(props) < k["test_attempts"]:
            if jobs and h_job > k["max_hours_per_job"]:
                return "kill", f"{h_job:.1f} h of my time per job > 3 h (01 §2)"
            return "extend", f"test running: {age}/{k['test_days']} days, {len(props)}/{k['test_attempts']} proposals"
        if net_usd_m < k["min_net_usd_month"]:
            return "kill", f"net {net_usd_m:.0f} USD/month < 100 after 6 weeks and {len(props)} proposals (01 §2)"
        if h_job > k["max_hours_per_job"]:
            return "kill", f"{h_job:.1f} h per job > 3 h (01 §2)"
    if name == "bank-promos":
        closed = [r for r in a if r["status"] in ("paid", "lost", "refused")]
        if len(closed) >= 2 and all(r["status"] in ("lost", "refused") for r in closed[-2:]):
            return "kill", "two bonuses in a row lost or refused (01 §9)"
        state = income.load_json(income.INCOME / "bank-promos" / "state.json", {})
        open_pln = state.get("eligible_bonus_pln")
        if open_pln is not None and open_pln < k["min_open_pln"]:
            return "kill", f"open offers for you total {open_pln:.0f} PLN < 1,500 PLN (01 §9; from the last promo fetch)"
    if name == "bailiff":
        buys = [r for r in a if r["status"] in ("bought", "sold")]
        sold = [r for r in buys if r["status"] == "sold"]
        stuck = [r for r in buys if r["status"] == "bought"
                 and (today - datetime.date.fromisoformat(r["date"])).days > k["stuck_days"]]
        if age < k["test_days"] or len(buys) < k["test_purchases"]:
            if stuck:
                return "extend", f"test running, but {len(stuck)} item(s) unsold for > {k['stuck_days']} days - watch capital"
            return "extend", f"test running: {age}/{k['test_days']} days, {len(buys)}/{k['test_purchases']} purchases"
        cost = sum(r["cost"] for r in sold)
        margin = (sum(r["revenue"] for r in sold) - cost) / cost if cost else 0
        if margin < k["min_margin"]:
            return "kill", f"net margin {margin:.0%} < 10% after {len(buys)} purchases (01 §6)"
        if stuck:
            return "kill", f"capital stuck: {len(stuck)} item(s) unsold for > {k['stuck_days']} days (01 §6)"
    # generic rules (02 §4)
    if len(a) >= 20 and not any(r["status"] in WINS for r in a):
        return "kill", f"{len(a)} attempts with zero wins - stop or change the method (02 §4)"
    if age >= 56:
        def per_h(lo, hi):
            rr = [r for r in a if lo < (today - datetime.date.fromisoformat(r["date"])).days <= hi]
            h = sum(r["hours_human"] for r in rr)
            return (sum(r["revenue"] - r["cost"] for r in rr) / usd / h) if h else None
        last, prev = per_h(-1, 28), per_h(28, 56)
        if last is not None and last < FLOOR_USD_H and (prev is None or last <= prev):
            return "kill", f"last 4 weeks {last:.0f} USD/h < 30 USD/h floor, no upward trend (02 §4)"
    return "keep", "passes its kill criteria"


def kill_check():
    today = income.today()
    usd, warn = usd_pln()
    out = []
    with db() as c:
        streams = [dict(r) for r in c.execute("SELECT * FROM streams ORDER BY name")]
    for s in streams:
        if s["status"] == "killed":
            out.append({"stream": s["name"], "verdict": "kill", "reason": "marked killed", "rule": KILL.get(s["name"], {}).get("rule", "")})
            continue
        v, why = _verdict_stream(s["name"], s["started"], rows(stream=s["name"]), today, usd)
        note = warn if s["name"] == "freelance" or "USD/h" in why else ""
        out.append({"stream": s["name"], "verdict": v, "reason": why + note, "rule": KILL.get(s["name"], {}).get("rule", "")})
    return out


def quarter_revenue(stream="bailiff"):
    t = income.today()
    q0 = datetime.date(t.year, 3 * ((t.month - 1) // 3) + 1, 1)
    return sum(r["revenue"] for r in rows(stream=stream, start=q0, end=t))


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0 if a else 2)
    p = argparse.ArgumentParser(prog="ledger.py", description=__doc__.split("\n\n")[0])
    sp = p.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("add-attempt")
    a.add_argument("--stream", required=True); a.add_argument("--item", required=True)
    a.add_argument("--date"); a.add_argument("--hours", type=float, default=0.0)
    a.add_argument("--cost", type=float, default=0.0); a.add_argument("--revenue", type=float, default=0.0)
    a.add_argument("--currency", default="PLN"); a.add_argument("--status", default="pending"); a.add_argument("--note", default="")
    u = sp.add_parser("update")
    u.add_argument("id", type=int); u.add_argument("--status"); u.add_argument("--hours", type=float)
    u.add_argument("--cost", type=float); u.add_argument("--revenue", type=float); u.add_argument("--note")
    u.add_argument("--currency", default="PLN"); u.add_argument("--date")
    ls = sp.add_parser("list"); ls.add_argument("--stream"); ls.add_argument("--status"); ls.add_argument("--limit", type=int, default=30)
    sm = sp.add_parser("summary"); sm.add_argument("--month"); sm.add_argument("--days", type=int)
    sp.add_parser("kill-check")
    st = sp.add_parser("stream"); st.add_argument("name", choices=STREAMS); st.add_argument("--status", required=True, choices=("active", "paused", "killed"))
    x = p.parse_args(argv)

    if x.cmd == "add-attempt":
        i = add_attempt(x.stream, x.item, x.date, x.hours, x.cost, x.revenue, x.status, x.note, x.currency)
        print(f"OK attempt {i} added to {x.stream} ({x.status}). Update later: ledger.py update {i} --status ...")
    elif x.cmd == "update":
        r = update(x.id, x.status, x.hours, x.cost, x.revenue, x.note, x.currency, x.date)
        print(f"OK attempt {r['id']}: {r['stream']} {r['status']} revenue {r['revenue']:.2f} PLN cost {r['cost']:.2f} PLN hours {r['hours_human']}")
    elif x.cmd == "list":
        rr = [r for r in rows(x.stream) if not x.status or r["status"] == x.status][-x.limit:]
        for r in rr:
            print(f"{r['id']:>4} {r['date']} {r['stream']:<11} {r['status']:<11} {r['revenue'] - r['cost']:>8.2f} PLN "
                  f"{r['hours_human']:>4.1f} h  {r['item'][:60]}")
        print(f"OK {len(rr)} attempt(s)")
    elif x.cmd == "summary":
        t = income.today()
        if x.month:
            y, m = map(int, x.month.split("-"))
            start = datetime.date(y, m, 1)
            end = (start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        else:
            start, end = t - datetime.timedelta(days=(x.days or 28) - 1), t
        s = summarize(start, end)
        print(f"Period {start} .. {end} (PLN)")
        print(f"{'stream':<12}{'n':>4}{'wins':>5}{'revenue':>10}{'cost':>9}{'net':>10}{'hours':>7}{'PLN/h':>8}")
        tot = {"n": 0, "wins": 0, "revenue": 0, "cost": 0, "net": 0, "hours": 0}
        for k, v in sorted(s.items(), key=lambda kv: -(kv[1]["pln_h"] or -1e9)):
            print(f"{k:<12}{v['n']:>4}{v['wins']:>5}{v['revenue']:>10.2f}{v['cost']:>9.2f}{v['net']:>10.2f}{v['hours']:>7.1f}"
                  f"{(v['pln_h'] if v['pln_h'] is not None else float('nan')):>8.1f}")
            for f in tot:
                tot[f] += v[f]
        print(f"{'TOTAL':<12}{tot['n']:>4}{tot['wins']:>5}{tot['revenue']:>10.2f}{tot['cost']:>9.2f}{tot['net']:>10.2f}{tot['hours']:>7.1f}")
        q = quarter_revenue()
        if q:
            print(f"Bailiff resale revenue this quarter: {q:.2f} of {QUARTER_LIMIT_PLN} PLN unregistered-activity limit (03 §1.1)")
        print(f"OK {len(s)} stream(s)")
    elif x.cmd == "kill-check":
        res = kill_check()
        for r in res:
            print(f"{r['verdict'].upper():<7} {r['stream']:<12} {r['reason']}")
        print(f"Generic rules: {GENERIC}")
        bad = [r for r in res if r["verdict"] in ("kill", "pause")]
        print(f"{'WARN' if bad else 'OK'} {len(res)} stream(s) checked, {len(bad)} to kill/pause" if res else
              "OK no streams yet - add the first attempt with: ledger.py add-attempt --stream claims --item ...")
    elif x.cmd == "stream":
        with db() as c:
            c.execute("INSERT OR IGNORE INTO streams(name, started) VALUES (?,?)", (x.name, str(income.today())))
            c.execute("UPDATE streams SET status=? WHERE name=?", (x.status, x.name))
        print(f"OK stream {x.name} -> {x.status}")


if __name__ == "__main__":
    main()
