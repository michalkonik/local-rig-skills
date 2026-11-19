#!/usr/bin/env python3
"""MEXC spot, read only. Secrets: bw-secret mexc#key and mexc#secret.

Never print the key, secret, or signature. No orders, transfers, or withdrawals.
"""
import argparse, datetime, hashlib, hmac, json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

API = "https://api.mexc.com"
ITEM = "mexc"
WARSAW = ZoneInfo("Europe/Warsaw")
WINDOW_MS = 29 * 86400 * 1000


class GiveUp(SystemExit):
    pass


def say(text, code=1):
    print(scrub(text))
    raise GiveUp(code)


def scrub(text):
    text = re.sub(r"(?i)(key|secret|sign|signature)(['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9+/=]{16,}", r"\1\2<redacted>", text)
    return text


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


def sign(secret, query):
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


def api(path, query):
    key, secret = bw_secret("key"), bw_secret("secret")
    params = [(k, v) for k, v in query if v not in (None, "")]
    params.append(("timestamp", str(int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000))))
    params.append(("recvWindow", "5000"))
    encoded = urllib.parse.urlencode(params)
    url = API + path + "?" + encoded + "&signature=" + sign(secret, encoded)
    req = urllib.request.Request(url, method="GET", headers={"X-MEXC-APIKEY": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        msg = raw[:240].replace("\n", " ")
        try:
            err = json.loads(raw)
            msg = str(err.get("msg") or err.get("message") or msg)[:240]
        except json.JSONDecodeError:
            pass
        say(f"ERROR {e.code} {msg}")


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


def nonzero(amount):
    try:
        return float(amount or 0) != 0
    except ValueError:
        return True


def local_time(value):
    try:
        stamp = int(float(value))
    except (TypeError, ValueError):
        return str(value or "-")
    if stamp > 10_000_000_000:
        stamp //= 1000
    return datetime.datetime.fromtimestamp(stamp, WARSAW).strftime("%Y-%m-%d %H:%M")


def cmd_balance(args):
    data = api("/api/v3/account", [])
    rows = data.get("balances") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        say("ERROR account response had no balances")
    wanted = args.asset.upper() if args.asset else ""
    shown = []
    for row in rows:
        asset = row.get("asset") or ""
        if wanted and asset != wanted:
            continue
        if wanted or args.all or nonzero(row.get("free")) or nonzero(row.get("locked")):
            shown.append(row)
    print(f"OK mexc spot {len(shown)} shown of {len(rows)}")
    for row in sorted(shown, key=lambda r: r.get("asset") or ""):
        print(f"- {row.get('asset')} free {row.get('free')} locked {row.get('locked')}")
    if not shown:
        print("(none)")


def rows_of(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "rows", "list"):
            if isinstance(data.get(key), list):
                return data[key]
    say("ERROR history response was not a list")


def cmd_trades(args):
    start, end = bounds(args.date_from, args.date_to)
    symbol = args.symbol.upper()
    rows = []
    for win_from, win_to in windows(start, end):
        query = [("symbol", symbol), ("startTime", win_from), ("endTime", win_to), ("limit", 100)]
        rows.extend(rows_of(api("/api/v3/myTrades", query)))
    rows.sort(key=lambda r: int(float(r.get("time") or 0)), reverse=True)
    print(f"OK mexc trades {symbol} {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        print(f"- {local_time(row.get('time'))} {'buy' if row.get('isBuyer') else 'sell'} {row.get('qty')} {symbol} price {row.get('price')} quote {row.get('quoteQty')} fee {row.get('commission')} {row.get('commissionAsset')}")
    if not rows:
        print("(none)")


def history(path, start, end):
    rows = []
    for win_from, win_to in windows(start, end):
        query = [("startTime", win_from), ("endTime", win_to), ("limit", 100)]
        rows.extend(rows_of(api(path, query)))
    rows.sort(key=lambda r: int(float(r.get("applyTime") or r.get("insertTime") or r.get("time") or 0)), reverse=True)
    return rows


def cmd_withdrawals(args):
    start, end = bounds(args.date_from, args.date_to)
    rows = history("/api/v3/capital/withdraw/history", start, end)
    print(f"OK mexc withdrawals {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        when = row.get("applyTime") or row.get("time")
        print(f"- {local_time(when)} {row.get('amount')} {row.get('coin')} {row.get('status')} fee {row.get('transactionFee')} {row.get('network')} address {mask(row.get('address'))} tx {mask(row.get('txId'))}")
    if not rows:
        print("(none)")


def cmd_deposits(args):
    start, end = bounds(args.date_from, args.date_to)
    rows = history("/api/v3/capital/deposit/hisrec", start, end)
    print(f"OK mexc deposits {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        when = row.get("insertTime") or row.get("time")
        print(f"- {local_time(when)} {row.get('amount')} {row.get('coin')} {row.get('status')} {row.get('network')} address {mask(row.get('address'))} tx {mask(row.get('txId'))}")
    if not rows:
        print("(none)")


def selftest():
    secret = "secret"
    query = "timestamp=1&recvWindow=5000"
    assert sign(secret, query) == hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    assert len(sign(secret, query)) == 64
    assert mask("TXYZ1234abcd") == "TXYZ••••abcd"
    start, end = bounds("2026-11-01", "2026-11-01")
    assert end > start
    assert list(windows(0, WINDOW_MS - 1)) == [(0, WINDOW_MS - 1)]
    print("OK selftest")


def build():
    parser = argparse.ArgumentParser(prog="mexc.py", description="MEXC spot read-only helper. Key stays in Bitwarden item mexc.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        command = sub.add_parser(name)
        command.set_defaults(fn=fn)
        return command

    balance = add("balance", cmd_balance)
    balance.add_argument("--asset", default="")
    balance.add_argument("--all", action="store_true")
    trades = add("trades", cmd_trades)
    trades.add_argument("--symbol", required=True)
    trades.add_argument("--from", dest="date_from", required=True)
    trades.add_argument("--to", dest="date_to", required=True)
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
