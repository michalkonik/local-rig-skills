#!/usr/bin/env python3
"""Gate.io read-only helper. Secrets: bw-secret gateio#key and gateio#secret.

Never print the key, secret, or signature. No orders, transfers, or withdrawals.
"""
import argparse, datetime, hashlib, hmac, json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

API = "https://api.gateio.ws"
PREFIX = "/api/v4"
ITEM = "gateio"
WARSAW = ZoneInfo("Europe/Warsaw")
EMPTY_HASH = "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
WINDOW = 29 * 86400


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


def sign_headers(method, path, query, body, key, secret, timestamp):
    payload = hashlib.sha512((body or "").encode()).hexdigest()
    signed = f"{method}\n{path}\n{query}\n{payload}\n{timestamp}"
    signature = hmac.new(secret.encode(), signed.encode(), hashlib.sha512).hexdigest()
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": key,
        "Timestamp": timestamp,
        "SIGN": signature,
    }


def api(path, query=None):
    key, secret = bw_secret("key"), bw_secret("secret")
    q = urllib.parse.urlencode([(k, v) for k, v in (query or []) if v not in (None, "")])
    url = API + path + (("?" + q) if q else "")
    headers = sign_headers("GET", path, q, "", key, secret, str(int(datetime.datetime.now(datetime.timezone.utc).timestamp())))
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        msg = raw[:240].replace("\n", " ")
        try:
            err = json.loads(raw)
            msg = str(err.get("message") or err.get("label") or msg)[:240]
        except json.JSONDecodeError:
            pass
        say(f"ERROR {e.code} {msg}")


def bounds(date_from, date_to):
    try:
        start = datetime.datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=WARSAW)
        end_day = datetime.datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=WARSAW)
    except ValueError:
        say("ERROR dates must be YYYY-MM-DD", 2)
    end = end_day + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    if end < start:
        say("ERROR from is after to", 2)
    return int(start.timestamp()), int(end.timestamp())


def windows(start, end):
    cur = start
    while cur <= end:
        yield cur, min(end, cur + WINDOW - 1)
        cur += WINDOW


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
    query = [("currency", args.currency.upper())] if args.currency else []
    rows = api(PREFIX + "/spot/accounts", query)
    if not isinstance(rows, list):
        say("ERROR spot accounts response was not a list")
    shown = []
    for row in rows:
        if args.currency or args.all or nonzero(row.get("available")) or nonzero(row.get("locked")):
            shown.append(row)
    print(f"OK gate spot {len(shown)} shown of {len(rows)}")
    for row in sorted(shown, key=lambda r: r.get("currency") or ""):
        print(f"- {row.get('currency')} available {row.get('available')} locked {row.get('locked')}")
    if not shown:
        print("(none)")


def cmd_ledger(args):
    start, end = bounds(args.date_from, args.date_to)
    rows = []
    for win_from, win_to in windows(start, end):
        page = 1
        while page <= 10:
            query = [("currency", args.currency.upper() if args.currency else ""),
                     ("from", win_from), ("to", win_to), ("page", page), ("limit", 100)]
            chunk = api(PREFIX + "/spot/account_book", query)
            if not isinstance(chunk, list):
                say("ERROR ledger response was not a list")
            rows.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        else:
            print("WARN ledger was cut at 10 pages in one window")
    rows.sort(key=lambda r: int(float(r.get("time") or 0)), reverse=True)
    print(f"OK gate ledger {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        text = re.sub(r"\s+", " ", str(row.get("text") or "")).strip()[:80]
        print(f"- {local_time(row.get('time'))} {row.get('currency')} {row.get('change')} balance {row.get('balance')} {row.get('type')} {text}".rstrip())
    if not rows:
        print("(none)")


def cmd_trades(args):
    start, end = bounds(args.date_from, args.date_to)
    pair = args.pair.upper()
    rows = []
    for win_from, win_to in windows(start, end):
        page = 1
        while page <= 10:
            query = [("currency_pair", pair), ("from", win_from), ("to", win_to), ("page", page), ("limit", 100)]
            chunk = api(PREFIX + "/spot/my_trades", query)
            if not isinstance(chunk, list):
                say("ERROR trades response was not a list")
            rows.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        else:
            print("WARN trades were cut at 10 pages in one window")
    rows.sort(key=lambda r: int(float(r.get("create_time") or r.get("create_time_ms") or 0)), reverse=True)
    print(f"OK gate trades {pair} {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        when = row.get("create_time_ms") or row.get("create_time")
        print(f"- {local_time(when)} {row.get('side')} {row.get('amount')} {row.get('currency_pair')} price {row.get('price')} fee {row.get('fee')} {row.get('fee_currency')}")
    if not rows:
        print("(none)")


def list_wallet(path, start, end):
    rows = []
    for win_from, win_to in windows(start, end):
        offset = 0
        pages = 0
        while pages < 10:
            pages += 1
            query = [("from", win_from), ("to", win_to), ("limit", 100), ("offset", offset)]
            chunk = api(PREFIX + path, query)
            if not isinstance(chunk, list):
                say("ERROR wallet response was not a list")
            rows.extend(chunk)
            if len(chunk) < 100:
                break
            offset += 100
        else:
            print("WARN wallet list was cut at 10 pages in one window")
    return rows


def cmd_withdrawals(args):
    start, end = bounds(args.date_from, args.date_to)
    rows = list_wallet("/wallet/withdrawals", start, end)
    rows.sort(key=lambda r: int(float(r.get("timestamp") or 0)), reverse=True)
    print(f"OK gate withdrawals {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        print(f"- {local_time(row.get('timestamp'))} {row.get('amount')} {row.get('currency')} {row.get('status')} fee {row.get('fee')} {row.get('chain')} address {mask(row.get('address'))} tx {mask(row.get('txid'))}")
    if not rows:
        print("(none)")


def cmd_deposits(args):
    start, end = bounds(args.date_from, args.date_to)
    rows = list_wallet("/wallet/deposits", start, end)
    rows.sort(key=lambda r: int(float(r.get("timestamp") or 0)), reverse=True)
    print(f"OK gate deposits {args.date_from} to {args.date_to} {len(rows)}")
    for row in rows:
        print(f"- {local_time(row.get('timestamp'))} {row.get('amount')} {row.get('currency')} {row.get('status')} {row.get('chain')} address {mask(row.get('address'))} tx {mask(row.get('txid'))}")
    if not rows:
        print("(none)")


def selftest():
    assert hashlib.sha512(b"").hexdigest() == EMPTY_HASH
    headers = sign_headers("GET", "/api/v4/spot/accounts", "", "", "key", "secret", "1541993715")
    assert headers["KEY"] == "key"
    assert re.fullmatch(r"[0-9a-f]{128}", headers["SIGN"])
    assert mask("PL61109010140000071219812874") == "PL61••••2874"
    assert mask("abc") == "••••"
    start, end = bounds("2026-11-01", "2026-11-01")
    assert end > start
    assert list(windows(0, WINDOW - 1)) == [(0, WINDOW - 1)]
    print("OK selftest")


def build():
    parser = argparse.ArgumentParser(prog="gate.py", description="Gate.io read-only helper. Key stays in Bitwarden item gateio.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        command = sub.add_parser(name)
        command.set_defaults(fn=fn)
        return command

    balance = add("balance", cmd_balance)
    balance.add_argument("--currency", default="")
    balance.add_argument("--all", action="store_true")
    ledger = add("ledger", cmd_ledger)
    ledger.add_argument("--from", dest="date_from", required=True)
    ledger.add_argument("--to", dest="date_to", required=True)
    ledger.add_argument("--currency", default="")
    trades = add("trades", cmd_trades)
    trades.add_argument("--pair", required=True)
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
