#!/usr/bin/env python3
"""OKX read-only helper. Secrets: bw-secret okx#key, okx#secret, and okx#passphrase.

Never print the key, secret, passphrase, or signature. No orders, transfers, or withdrawals.
"""
import argparse, base64, datetime, hashlib, hmac, json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

API = "https://www.okx.com"
ITEM = "okx"
WARSAW = ZoneInfo("Europe/Warsaw")
WINDOW_MS = 7 * 86400 * 1000


class GiveUp(SystemExit):
    pass


def say(text, code=1):
    print(scrub(text))
    raise GiveUp(code)


def scrub(text):
    return re.sub(
        r"(?i)(key|secret|passphrase|sign|signature)(['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9+/=_-]{8,}",
        r"\1\2<redacted>",
        text,
    )


def mask(value):
    raw = re.sub(r"\s+", "", str(value or ""))
    if len(raw) < 8:
        return "••••" if raw else "-"
    return raw[:4] + "••••" + raw[-4:]


def bw_env():
    env = os.environ.copy()
    if not env.get("BW_SESSION"):
        path = os.path.expanduser("~/.config/bw/session")
        if os.path.isfile(path):
            env["BW_SESSION"] = open(path).read().strip()
    if not env.get("BW_SESSION"):
        say("ERROR vault: Bitwarden session is locked. Unlock it, then retry.")
    return env


def bw_secret(field):
    proc = subprocess.run(["bw-secret", f"{ITEM}#{field}"], capture_output=True, env=bw_env())
    if proc.returncode != 0:
        msg = proc.stderr.decode(errors="replace").strip().splitlines()
        say(f"ERROR vault: {ITEM}#{field} ({msg[-1][:120] if msg else 'not found'})")
    return proc.stdout.decode().strip()


def sign(secret, stamp, method, path, body=""):
    message = f"{stamp}{method.upper()}{path}{body}"
    return base64.b64encode(hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()).decode()


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def api(path, query=None):
    key, secret, passphrase = bw_secret("key"), bw_secret("secret"), bw_secret("passphrase")
    pairs = [(k, v) for k, v in (query or []) if v not in (None, "")]
    encoded = urllib.parse.urlencode(pairs)
    request_path = path + (("?" + encoded) if encoded else "")
    stamp = timestamp()
    signature = sign(secret, stamp, "GET", request_path, "")
    req = urllib.request.Request(
        API + request_path,
        method="GET",
        headers={
            "User-Agent": "local-rig-skills/okx",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": stamp,
            "OK-ACCESS-PASSPHRASE": passphrase,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        msg = raw[:240].replace("\n", " ")
        try:
            err = json.loads(raw)
            msg = str(err.get("msg") or err.get("message") or msg)[:240]
            say(f"ERROR {err.get('code') or e.code} {msg}")
        except json.JSONDecodeError:
            say(f"ERROR {e.code} {msg}")
    body = json.loads(raw) if raw else {}
    if str(body.get("code", "0")) != "0":
        say(f"ERROR {body.get('code')} {str(body.get('msg') or '')[:240]}")
    data = body.get("data")
    return data if isinstance(data, list) else []


def bounds(date_from, date_to):
    try:
        start = datetime.datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=WARSAW)
        end_day = datetime.datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=WARSAW)
    except ValueError:
        say("ERROR dates must be YYYY-MM-DD", 2)
    end = end_day + datetime.timedelta(days=1) - datetime.timedelta(milliseconds=1)
    if end < start:
        say("ERROR from is after to", 2)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def windows(start, end):
    cur = start
    while cur <= end:
        yield cur, min(end, cur + WINDOW_MS - 1)
        cur += WINDOW_MS


def nonzero(*amounts):
    for amount in amounts:
        try:
            if float(amount or 0) != 0:
                return True
        except ValueError:
            return True
    return False


def local_time(value):
    try:
        stamp = int(float(value))
    except (TypeError, ValueError):
        return str(value or "-")
    if stamp > 10_000_000_000:
        stamp //= 1000
    return datetime.datetime.fromtimestamp(stamp, WARSAW).strftime("%Y-%m-%d %H:%M")


def collect(path, query, cursor_field):
    rows = []
    cursor = None
    for _ in range(20):
        page = list(query)
        if cursor:
            page.append(("after", cursor))
        batch = api(path, page)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 100:
            break
        nxt = str(batch[-1].get(cursor_field) or "")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
    return rows


def cmd_balance(args):
    wanted = args.ccy.upper() if args.ccy else ""
    trading = api("/api/v5/account/balance", [])
    details = []
    for account in trading:
        details.extend(account.get("details") or [])
    shown = []
    for row in details:
        ccy = row.get("ccy") or ""
        if wanted and ccy != wanted:
            continue
        if wanted or args.all or nonzero(row.get("availBal"), row.get("frozenBal"), row.get("cashBal"), row.get("eq")):
            shown.append(row)
    print(f"OK okx trading {len(shown)} shown of {len(details)}")
    for row in sorted(shown, key=lambda r: r.get("ccy") or ""):
        print(f"- {row.get('ccy')} available {row.get('availBal')} frozen {row.get('frozenBal')}")
    if not shown:
        print("(none)")
    funding = api("/api/v5/asset/balances", [("ccy", wanted)] if wanted else [])
    fund_shown = []
    for row in funding:
        ccy = row.get("ccy") or ""
        if wanted and ccy != wanted:
            continue
        if wanted or args.all or nonzero(row.get("availBal"), row.get("frozenBal"), row.get("bal")):
            fund_shown.append(row)
    print(f"OK okx funding {len(fund_shown)} shown of {len(funding)}")
    for row in sorted(fund_shown, key=lambda r: r.get("ccy") or ""):
        print(f"- {row.get('ccy')} available {row.get('availBal')} frozen {row.get('frozenBal')}")
    if not fund_shown:
        print("(none)")


def cmd_bills(args):
    start, end = bounds(args.date_from, args.date_to)
    rows = []
    for win_from, win_to in windows(start, end):
        query = [("begin", str(win_from)), ("end", str(win_to)), ("limit", "100")]
        if args.ccy:
            query.append(("ccy", args.ccy.upper()))
        rows.extend(collect("/api/v5/account/bills-archive", query, "billId"))
    rows.sort(key=lambda r: int(float(r.get("ts") or 0)), reverse=True)
    print(f"OK okx bills {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        print(f"- {local_time(row.get('ts'))} {row.get('ccy')} change {row.get('balChg')} bal {row.get('bal')} type {row.get('type')} {row.get('instId') or '-'}")
    if not rows:
        print("(none)")


def cmd_fills(args):
    start, end = bounds(args.date_from, args.date_to)
    inst = args.inst.upper()
    rows = []
    for win_from, win_to in windows(start, end):
        query = [("instType", args.inst_type.upper()), ("instId", inst), ("begin", str(win_from)), ("end", str(win_to)), ("limit", "100")]
        rows.extend(collect("/api/v5/trade/fills-history", query, "billId"))
    rows.sort(key=lambda r: int(float(r.get("ts") or 0)), reverse=True)
    print(f"OK okx fills {inst} {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        print(f"- {local_time(row.get('ts'))} {row.get('side')} {row.get('fillSz')} {inst} price {row.get('fillPx')} fee {row.get('fee')} {row.get('feeCcy')}")
    if not rows:
        print("(none)")


def wallet(path, date_from, date_to, label):
    start, end = bounds(date_from, date_to)
    rows = collect(path, [("before", str(start)), ("after", str(end)), ("limit", "100")], "ts")
    kept = []
    for row in rows:
        try:
            stamp = int(float(row.get("ts") or 0))
        except ValueError:
            continue
        if start <= stamp <= end:
            kept.append(row)
    kept.sort(key=lambda r: int(float(r.get("ts") or 0)), reverse=True)
    print(f"OK okx {label} {date_from} to {date_to} {len(kept)}")
    for row in kept:
        print(f"- {local_time(row.get('ts'))} {row.get('amt')} {row.get('ccy')} state {row.get('state')} fee {row.get('fee') or '-'} {row.get('chain') or '-'} address {mask(row.get('to'))} tx {mask(row.get('txId'))}")
    if not kept:
        print("(none)")


def cmd_withdrawals(args):
    wallet("/api/v5/asset/withdrawal-history", args.date_from, args.date_to, "withdrawals")


def cmd_deposits(args):
    wallet("/api/v5/asset/deposit-history", args.date_from, args.date_to, "deposits")


def selftest():
    secret = "secret"
    stamp = "2020-12-08T09:08:57.715Z"
    path = "/api/v5/account/balance"
    message = stamp + "GET" + path
    expect = base64.b64encode(hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()).decode()
    assert sign(secret, stamp, "GET", path, "") == expect
    assert mask("TXYZ1234abcd") == "TXYZ••••abcd"
    start, end = bounds("2026-11-01", "2026-11-01")
    assert end > start
    assert list(windows(0, WINDOW_MS - 1)) == [(0, WINDOW_MS - 1)]
    hidden = scrub("secret=ABCDEFGHIJKLMNOP")
    assert "ABCDEFGHIJKLMNOP" not in hidden and "<redacted>" in hidden
    print("OK selftest")


def build():
    parser = argparse.ArgumentParser(prog="okx.py", description="OKX read-only helper. Key stays in Bitwarden item okx.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        command = sub.add_parser(name)
        command.set_defaults(fn=fn)
        return command

    balance = add("balance", cmd_balance)
    balance.add_argument("--ccy", default="")
    balance.add_argument("--all", action="store_true")
    bills = add("bills", cmd_bills)
    bills.add_argument("--from", dest="date_from", required=True)
    bills.add_argument("--to", dest="date_to", required=True)
    bills.add_argument("--ccy", default="")
    fills = add("fills", cmd_fills)
    fills.add_argument("--inst", required=True)
    fills.add_argument("--type", dest="inst_type", default="SPOT")
    fills.add_argument("--from", dest="date_from", required=True)
    fills.add_argument("--to", dest="date_to", required=True)
    for name, fn in (("withdrawals", cmd_withdrawals), ("deposits", cmd_deposits)):
        command = add(name, fn)
        command.add_argument("--from", dest="date_from", required=True)
        command.add_argument("--to", dest="date_to", required=True)
    add("selftest", lambda args: selftest())
    return parser


def main(argv=None):
    args = build().parse_args(argv)
    try:
        args.fn(args)
    except GiveUp as exc:
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
