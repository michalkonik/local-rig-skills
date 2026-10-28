#!/usr/bin/env python3
"""Thin wrapper around the Deal Hunter `dh` CLI: compact summaries for local models.

Usage: dh_skill.py status | deals [--tier N] [--since 2d|12h|2026-10-29] | show ID | explain ID | books | start | stop
Examples:
  dh_skill.py deals --tier 1 --since 2d
  dh_skill.py explain 7
Read-only except start/stop. Never edits config, never contacts sellers.
Exit codes: 0 ok, 1 error, 2 usage, 3 not found.
"""
import json, os, re, subprocess, sys
from datetime import datetime, timedelta, timezone

DH_DIR = os.path.expanduser("~/Desktop/github_repos/deal-hunter")
DH = os.path.join(DH_DIR, ".venv/bin/dh")
TIERS = {1: "T1 act now (>= $300 conservative net, high confidence)", 2: "T2 strong", 3: "T3 watch", 4: "T4 low"}


def run(args, as_json=True, timeout=100):
    if not os.path.exists(DH):
        sys.exit("ERROR dh not found at %s" % DH)
    cmd = [DH] + args + (["--json"] if as_json else [])
    try:
        p = subprocess.run(cmd, cwd=DH_DIR, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        sys.exit("ERROR dh %s timed out after %ss" % (" ".join(args), timeout))
    if p.returncode != 0:
        msg = (p.stdout + p.stderr).strip()
        print("ERROR dh %s failed (exit %d): %s" % (" ".join(args), p.returncode, msg[-600:]))
        sys.exit(3 if re.search(r"not found|no deal", msg.lower()) else 1)
    if not as_json:
        return (p.stdout + p.stderr).strip()
    try:
        return json.loads(p.stdout)
    except ValueError:
        sys.exit("ERROR dh printed non-JSON: %s" % p.stdout[:300])


def m(x, cur="$"):
    try:
        return "%s%s" % (cur, format(round(float(x)), ","))
    except (TypeError, ValueError):
        return "?"


def parse_since(s):
    r = re.fullmatch(r"(\d+)([hd])", s)
    if r:
        n = int(r.group(1))
        return datetime.now(timezone.utc) - (timedelta(hours=n) if r.group(2) == "h" else timedelta(days=n))
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        sys.exit("ERROR bad --since %r. Use 2d, 12h or 2026-10-29. Retry: dh_skill.py deals --since 2d" % s)


def cmd_status(_):
    d = run(["status"])
    lr = d.get("last_round") or {}
    dt = d.get("deals_today") or {}
    h = d.get("health") or {}
    print("Deal Hunter: %s (unit %s)%s" % ("RUNNING" if d.get("running") else "stopped", d.get("state"),
          ", up %d min" % (d["uptime_s"] // 60) if d.get("uptime_s") else ""))
    print("Rounds: %s total, %s since start; watched %.1f h" % (d.get("rounds_total"), d.get("rounds_since_start"), d.get("watched_hours") or 0))
    if lr:
        try:
            end = datetime.fromisoformat(lr["ended_at"]).astimezone().strftime("%Y-%m-%d %H:%M")
        except (KeyError, TypeError, ValueError):
            end = "?"
        print("Last round #%s ended %s (took %s s): %s arms, %s listings seen, deals by tier %s, errors %s" % (
            lr.get("id"), end, round(lr.get("seconds") or 0), lr.get("arms"), lr.get("listings_seen"),
            lr.get("deals_by_tier"), lr.get("errors")))
    print("Deals today: %s" % (json.dumps(dt) if dt else "none"))
    print("Health: blocked=%s disabled=%s; cost today %s PLN" % (h.get("blocked") or "none", h.get("disabled") or "none", d.get("cost_today_pln")))
    print("Models loaded in llama-swap: %s" % (", ".join((d.get("llama_swap") or {}).get("running") or []) or "none"))
    print("OK status")


def cmd_deals(a):
    tier, since = None, None
    i = 0
    while i < len(a):
        if a[i] == "--tier" and i + 1 < len(a):
            tier = a[i + 1]; i += 2
        elif a[i] == "--since" and i + 1 < len(a):
            since = parse_since(a[i + 1]); i += 2
        else:
            sys.exit("usage: dh_skill.py deals [--tier 1-4] [--since 2d|12h|YYYY-MM-DD]")
    if tier and tier not in "1234":
        sys.exit("ERROR --tier must be 1, 2, 3 or 4")
    args = ["deals"] + (["--tier", tier] if tier else [])
    rows = run(args)
    if since:
        rows = [r for r in rows if datetime.fromisoformat(r["created_at"]) >= since]
    for r in rows[:15]:
        l = r.get("listing") or {}
        print("#%s T%s%s net %s (exp %s) cap %s | %s conf, %s effort | %s %s %s | %s" % (
            r["id"], r["tier"], "*" if r.get("star") else "", m(r["cons_net_usd"]), m(r["exp_net_usd"]),
            m(r["capital_usd"]), r.get("confidence"), r.get("effort"), l.get("source"), l.get("price"),
            l.get("currency"), (l.get("title") or "")[:50]))
    if len(rows) > 15:
        print("... %d more" % (len(rows) - 15))
    print("OK %d deals (net = conservative net USD; * = starred)" % len(rows))


def cmd_show(a):
    d = run(["show", a[0]])
    l = d.get("listing") or {}
    print("Deal #%s [%s] T%s%s, status %s, %s confidence, %s effort" % (
        d["deal_id"], d.get("key"), d["tier"], "*" if d.get("star") else "", d.get("status"), d.get("confidence"), d.get("effort")))
    print("Listing: %s | %s %s (%s) | %s" % (l.get("title"), l.get("price"), l.get("currency"), l.get("country"), l.get("url")))
    print("Buy %s PLN -> exit p25 %s / median %s PLN" % (m(d.get("buy_pln"), ""), m(d.get("exit_p25_pln"), ""), m(d.get("exit_median_pln"), "")))
    print("Net: conservative %s (%s PLN), expected %s (%s PLN); capital %s" % (
        m(d["cons_net_usd"]), m(d["cons_net_pln"], ""), m(d["exp_net_usd"]), m(d["exp_net_pln"], ""), m(d["capital_usd"])))
    print("Comparables: %d; scam risk %.1f%% flags %s; verified live: %s" % (
        len(d.get("comps") or []), 100 * (d.get("risk") or {}).get("p_scam", 0), (d.get("risk") or {}).get("flags") or "none", d.get("verified_at") or "no"))
    print("OK show (use explain %s for the breakdown)" % d["deal_id"])


def cmd_explain(a):
    d = run(["show", a[0]])
    print("Deal #%s, tier %d: %s" % (d["deal_id"], d["tier"], TIERS.get(d["tier"], "?")))
    print("Why this tier:")
    seen = set()
    for r in d.get("reasons") or []:
        key = re.sub(r"^(confidence:) (?:low|high|medium): ", r"\1 ", r)
        if key in seen:
            continue
        seen.add(key)
        print("  - %s" % r)
    print("Conservative net, step by step (PLN; exit uses the 25th-percentile price):")
    for b in (d.get("breakdown") or {}).get("cons", []):
        print("  %s %s  (%s)" % (("%+.0f" % float(b["pln"])).rjust(7), b["label"], b.get("note", "")[:70]))
    print("  = %s PLN net = %s USD" % (m(d["cons_net_pln"], ""), m(d["cons_net_usd"], "")))
    rk = d.get("risk") or {}
    print("Risk: scam probability %.1f%%, flags: %s" % (100 * rk.get("p_scam", 0), ", ".join(rk.get("flags") or []) or "none"))
    cl = d.get("checklist") or []
    if cl:
        print("Before anyone acts (the owner, by hand):")
        for c in cl[:6]:
            print("  - %s" % (c if isinstance(c, str) else c.get("text") or c.get("label") or json.dumps(c)))
    print("OK explain")


def cmd_books(_):
    d = run(["books"])
    t = d.get("today") or {}
    a = d.get("all_time") or {}
    print("Today: %s PLN over %s rounds; all time: %s PLN over %s rounds" % (t.get("total_pln"), t.get("rounds"), a.get("total_pln"), a.get("rounds")))
    print("Costs today by kind (PLN): %s" % ", ".join("%s %s" % (k, v["pln"]) for k, v in (t.get("by_kind") or {}).items()))
    print("Watched %.1f h; deals by tier %s; forecast conservative net %s PLN" % (d.get("watched_hours") or 0, d.get("deals"), d.get("forecast_cons_net_pln")))
    print("OK books")


def cmd_start(_):
    out = run(["start"], as_json=False)
    print(out[-500:] or "(no output)")
    print("OK start requested; check with: dh_skill.py status")


def cmd_stop(_):
    out = run(["stop"], as_json=False)
    print(out[-500:] or "(no output)")
    print("OK stop requested")


CMDS = {"status": cmd_status, "deals": cmd_deals, "show": cmd_show, "explain": cmd_explain,
        "books": cmd_books, "start": cmd_start, "stop": cmd_stop}

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help") or a[0] not in CMDS:
        print(__doc__); sys.exit(2 if a and a[0] not in ("-h", "--help") else 0)
    if a[0] in ("show", "explain") and (len(a) != 2 or not a[1].isdigit()):
        sys.exit("usage: dh_skill.py %s ID   (ID is a number from `deals`)" % a[0])
    CMDS[a[0]](a[1:])
