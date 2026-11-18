#!/usr/bin/env python3
"""PKO via Enable Banking. Secrets: bw-secret enablebanking-pko#app_id and #private_key.

Never print the private key, JWT, or a full account number. Read-only except
`session`, which stores the consented session id in the same vault item.
"""
import argparse, base64, datetime, json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

API = "https://api.enablebanking.com"
TOKEN = None
ITEM = "enablebanking-pko"
ASPSP = {"name": "PKO Bank Polski", "country": "PL"}
DUE_HINTS = ("termin", "due", "spłat", "splat", "payment date", "pay by", "odset", "repay")


class GiveUp(SystemExit):
    pass


def say(text, code=1):
    print(scrub(text))
    raise GiveUp(code)


def scrub(text):
    text = re.sub(r"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----", "<redacted>", text, flags=re.S)
    text = re.sub(r"\bPL\d{10,}\b", "PL••••", text)
    return text


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def redirect_ok(url):
    parsed = urllib.parse.urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if host in {"", "example.com", "www.example.com"}:
        return False
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and host in {"localhost", "127.0.0.1"}


def mask_account(account):
    ident = account.get("account_id") or {}
    raw = ""
    if isinstance(ident, dict):
        raw = ident.get("iban") or ((ident.get("other") or {}).get("identification") or "")
    digits = re.sub(r"\s+", "", str(raw))
    tail = digits[-4:] if len(digits) >= 4 else "????"
    return "••••" + tail


def due_from_balances(balances):
    for row in balances or []:
        name = (row.get("name") or "").lower()
        ref = (row.get("reference_date") or "")[:10]
        if ref and any(hint in name for hint in DUE_HINTS):
            return ref, row.get("name") or "due"
    return None, None


def days_until(date_text, today):
    return (datetime.date.fromisoformat(date_text) - today).days


def bw_env():
    env = os.environ.copy()
    if not env.get("BW_SESSION"):
        path = os.path.expanduser("~/.config/bw/session")
        if os.path.isfile(path):
            env["BW_SESSION"] = open(path).read().strip()
    if not env.get("BW_SESSION"):
        say("ERROR vault: Bitwarden session is locked. Unlock it, then retry.")
    return env


def bw_secret(field, missing_ok=False):
    proc = subprocess.run(["bw-secret", f"{ITEM}#{field}"], capture_output=True, env=bw_env())
    if proc.returncode != 0:
        if missing_ok:
            return ""
        msg = proc.stderr.decode(errors="replace").strip().splitlines()
        say(f"ERROR vault: {ITEM}#{field} ({msg[-1][:120] if msg else 'not found'})")
    return proc.stdout.decode()


def sign_jwt(app_id, pem):
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    header = b64url(json.dumps({"typ": "JWT", "alg": "RS256", "kid": app_id}, separators=(",", ":")).encode())
    body = b64url(json.dumps({
        "iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": now, "exp": now + 600,
    }, separators=(",", ":")).encode())
    signing = f"{header}.{body}".encode()
    sig = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return signing.decode() + "." + b64url(sig)


def app_token():
    global TOKEN
    if not TOKEN:
        TOKEN = sign_jwt(bw_secret("app_id").strip(), bw_secret("private_key"))
    return TOKEN


def api(method, path, query=None, body=None, token=None):
    token = token or app_token()
    url = API + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        msg = raw[:240].replace("\n", " ")
        try:
            err = json.loads(raw)
            msg = str(err.get("message") or err.get("detail") or err.get("error") or msg)[:240]
        except json.JSONDecodeError:
            pass
        say(f"ERROR {e.code} {msg}")


NO_SESSION = ("ERROR no session. The app key works, but linking the account in the control panel does not "
             "create an API session. Add a redirect URL you control (not example.com), then run "
             "pko.py auth --redirect URL and pko.py session --code CODE.")


def load_accounts():
    saved = bw_secret("accounts_json", missing_ok=True).strip()
    if saved:
        return json.loads(saved)
    sid = bw_secret("session_id", missing_ok=True).strip()
    if not sid:
        say(NO_SESSION)
    data = api("GET", "/sessions/" + urllib.parse.quote(sid, safe=""))
    return data.get("accounts") or []


def account_rows(accounts, hint):
    rows = []
    for account in accounts:
        rows.append(account)
    if not hint:
        return rows
    hint_l = hint.lower()
    picked = [a for a in rows if hint_l in json.dumps({
        "product": a.get("product"), "type": a.get("cash_account_type") or a.get("type"),
        "mask": a.get("mask") or mask_account(a), "name": a.get("name"),
    }, ensure_ascii=False).lower() or hint_l in mask_account(a)]
    if not picked:
        say("ERROR no account matched that hint", 3)
    return picked


def uid_of(account):
    return account.get("uid") or account.get("account_uid")


def label(account):
    kind = account.get("cash_account_type") or account.get("type") or "account"
    product = account.get("product") or ""
    mask = account.get("mask") or mask_account(account)
    extra = f" {product}" if product else ""
    limit = account.get("credit_limit")
    if isinstance(limit, dict):
        limit = limit.get("amount")
    lim = f" limit {limit} {account.get('currency') or ''}".rstrip() if limit else ""
    return f"{kind}{extra} {mask}{lim}".strip()


def cmd_status(_args):
    app = api("GET", "/application")
    redirects = ", ".join(app.get("redirect_urls") or [])
    print(f"OK app {app.get('name')} {app.get('environment')} active {app.get('active')} services {','.join(app.get('services') or [])}")
    print(f"OK redirects {redirects or '(none)'}")
    if "example.com" in redirects and redirects.strip() in {"https://example.com/callback", "http://example.com/callback"}:
        print("WARN the only redirect is example.com. Do not send the bank login there. Register a URL you control first.")
    sid = bw_secret("session_id", missing_ok=True).strip()
    if not sid:
        print("OK no session")
        return
    data = api("GET", "/sessions/" + urllib.parse.quote(sid, safe=""))
    accounts = data.get("accounts") or []
    print(f"OK session accounts {len(accounts)} status {data.get('status') or 'present'}")


def cmd_balance(args):
    accounts = account_rows(load_accounts(), args.account)
    if not accounts:
        say("ERROR no PKO accounts in the session")
    for account in accounts:
        uid = uid_of(account)
        if not uid:
            say("ERROR account has no uid. Re-run session --code while the code is fresh.")
        data = api("GET", "/accounts/" + urllib.parse.quote(uid, safe="") + "/balances")
        print(f"OK balance {label(account)}")
        for row in data.get("balances") or []:
            amount = (row.get("balance_amount") or {})
            ref = row.get("reference_date") or "-"
            print(f"- {row.get('name')} {row.get('balance_type')} {amount.get('amount')} {amount.get('currency')} ref {ref}")


def tx_text(row):
    rem = row.get("remittance_information") or row.get("remittance_information_unstructured") or ""
    if isinstance(rem, list):
        rem = " ".join(str(x) for x in rem)
    elif isinstance(rem, dict):
        rem = " ".join(str(v) for v in rem.values())
    rem = re.sub(r"\s+", " ", str(rem)).strip()[:80]
    party = ((row.get("creditor") or {}).get("name") or (row.get("debtor") or {}).get("name") or "").strip()
    return party, rem


def cmd_transactions(args):
    try:
        datetime.date.fromisoformat(args.date_from)
        datetime.date.fromisoformat(args.date_to)
    except ValueError:
        say("ERROR dates must be YYYY-MM-DD", 2)
    if args.date_from > args.date_to:
        say("ERROR from is after to", 2)
    accounts = account_rows(load_accounts(), args.account)
    for account in accounts:
        uid = uid_of(account)
        if not uid:
            say("ERROR account has no uid. Re-run session --code while the code is fresh.")
        rows, token, pages = [], None, 0
        while pages < 5:
            pages += 1
            query = {"date_from": args.date_from, "date_to": args.date_to}
            if token:
                query["continuation_key"] = token
            data = api("GET", "/accounts/" + urllib.parse.quote(uid, safe="") + "/transactions", query)
            rows.extend(data.get("transactions") or [])
            token = data.get("continuation_key")
            if not token:
                break
        else:
            print("WARN list was cut at 5 pages")
        inn = out = 0.0
        parsed = []
        for row in rows:
            amount = row.get("transaction_amount") or {}
            try:
                value = float(amount.get("amount") or 0)
            except ValueError:
                value = 0.0
            if (amount.get("currency") or "PLN") == "PLN":
                if value >= 0:
                    inn += value
                else:
                    out += abs(value)
            party, rem = tx_text(row)
            when = row.get("booking_date") or row.get("value_date") or "-"
            parsed.append((when, value, amount.get("currency") or "", row.get("credit_debit_indicator") or "", party, rem, row.get("status") or ""))
        parsed.sort(reverse=True)
        print(f"OK transactions {label(account)} {args.date_from} to {args.date_to}")
        print(f"{len(parsed)} transactions. In: {inn:.2f} PLN. Out: {out:.2f} PLN.")
        for when, value, cur, side, party, rem, status in parsed:
            pending = " pending" if status and status not in {"BOOK", "BOOKED"} else ""
            print(f"- {when} {value:.2f} {cur} {side} {party} — {rem}{pending}".rstrip())
        if not parsed:
            print("(none)")


def cmd_card(args):
    accounts = account_rows(load_accounts(), args.account)
    cards = [a for a in accounts if (a.get("cash_account_type") or a.get("type")) == "CARD"
             or "kart" in (a.get("product") or "").lower() or "credit" in (a.get("product") or "").lower()]
    if not cards:
        say("ERROR no credit-card account in the session. Balance still works for the other accounts.")
    today = datetime.date.today()
    for account in cards:
        uid = uid_of(account)
        if not uid:
            say("ERROR card account has no uid. Re-run session --code while the code is fresh.")
        data = api("GET", "/accounts/" + urllib.parse.quote(uid, safe="") + "/balances")
        balances = data.get("balances") or []
        print(f"OK card {label(account)}")
        for row in balances:
            amount = row.get("balance_amount") or {}
            print(f"- {row.get('name')} {row.get('balance_type')} {amount.get('amount')} {amount.get('currency')} ref {row.get('reference_date') or '-'}")
        due, due_name = due_from_balances(balances)
        if not due:
            print("OK no due date in the bank feed. Days until interest were not computed.")
            continue
        left = days_until(due, today)
        if left >= 0:
            print(f"OK interest date {due} ({due_name}) in {left} days if that amount stays unpaid")
        else:
            print(f"OK interest date {due} ({due_name}) was {abs(left)} days ago")


def cmd_auth(args):
    if not redirect_ok(args.redirect):
        say("ERROR redirect must be an https URL you control, or http://127.0.0.1 / localhost. example.com would receive the bank code.", 2)
    valid = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=179)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    state = base64.urlsafe_b64encode(os.urandom(9)).decode().rstrip("=")
    data = api("POST", "/auth", body={
        "access": {"balances": True, "transactions": True, "valid_until": valid},
        "aspsp": ASPSP,
        "state": state,
        "redirect_url": args.redirect,
        "psu_type": args.psu_type,
        "language": "pl",
    })
    if not data.get("url"):
        say("ERROR auth returned no url")
    print(f"OK auth state {state}")
    print(data["url"])
    print("Open that URL, approve read-only access, then run: pko.py session --code CODE")


def save_fields(updates):
    env = bw_env()
    listed = json.loads(subprocess.run(["bw", "list", "items"], capture_output=True, env=env).stdout)
    hits = [i for i in listed if i.get("name") == ITEM]
    if len(hits) != 1:
        say("ERROR vault: enablebanking-pko is missing or duplicated")
    item_id = hits[0]["id"]
    got = subprocess.run(["bw", "get", "item", item_id], capture_output=True, env=env)
    if got.returncode != 0:
        say("ERROR vault: could not read the item for update")
    item = json.loads(got.stdout)
    fields = item.get("fields") or []
    by_name = {f.get("name"): f for f in fields}
    for name, value in updates.items():
        if name in by_name:
            by_name[name]["value"] = value
            by_name[name]["type"] = 1
        else:
            fields.append({"name": name, "value": value, "type": 1})
    item["fields"] = fields
    encoded = subprocess.run(["bw", "encode"], input=json.dumps(item).encode(), capture_output=True, env=env)
    edited = subprocess.run(["bw", "edit", "item", item_id], input=encoded.stdout, capture_output=True, env=env)
    if edited.returncode != 0:
        say("ERROR vault: could not store the session")


def shrink_account(account):
    limit = account.get("credit_limit") or {}
    if not isinstance(limit, dict):
        limit = {}
    return {
        "uid": account.get("uid"),
        "type": account.get("cash_account_type"),
        "currency": account.get("currency"),
        "product": account.get("product"),
        "credit_limit": limit.get("amount"),
        "mask": mask_account(account),
    }


def cmd_session(args):
    code = args.code.strip()
    if not code or "…" in code or "***" in code:
        say("ERROR code is empty or truncated", 2)
    data = api("POST", "/sessions", body={"code": code})
    sid = data.get("session_id") or ""
    accounts = [shrink_account(a) for a in (data.get("accounts") or [])]
    if not sid or not accounts:
        say("ERROR session response had no session or accounts")
    save_fields({"session_id": sid, "accounts_json": json.dumps(accounts)})
    kinds = ", ".join(sorted({a.get("type") or "?" for a in accounts}))
    print(f"OK session stored accounts {len(accounts)} types {kinds}")


def selftest():
    assert redirect_ok("https://example.com/callback") is False
    assert redirect_ok("http://evil.example/cb") is False
    assert redirect_ok("http://127.0.0.1:43821/cb") is True
    assert redirect_ok("https://bank.example.org/cb") is True
    assert days_until("2026-11-20", datetime.date(2026, 11, 18)) == 2
    due, name = due_from_balances([
        {"name": "closing booked", "reference_date": "2026-11-18"},
        {"name": "Termin spłaty", "reference_date": "2026-12-01"},
    ])
    assert due == "2026-12-01" and name == "Termin spłaty"
    assert due_from_balances([{"name": "available", "reference_date": "2026-11-18"}]) == (None, None)
    assert mask_account({"account_id": {"iban": "PL61109010140000071219812874"}}) == "••••2874"
    assert "PRIVATE KEY" not in scrub("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----")
    print("OK selftest")


def build():
    p = argparse.ArgumentParser(
        prog="pko.py",
        description="PKO read-only helper. Key stays in Bitwarden item enablebanking-pko.",
        epilog="examples: pko.py status | pko.py balance | pko.py card")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        return sp

    add("status", cmd_status)
    a = add("balance", cmd_balance)
    a.add_argument("--account", default="")
    a = add("transactions", cmd_transactions)
    a.add_argument("--from", dest="date_from", required=True)
    a.add_argument("--to", dest="date_to", required=True)
    a.add_argument("--account", default="")
    a = add("card", cmd_card)
    a.add_argument("--account", default="")
    a = add("auth", cmd_auth)
    a.add_argument("--redirect", required=True)
    a.add_argument("--psu-type", dest="psu_type", default="personal", choices=["personal", "business"])
    a = add("session", cmd_session)
    a.add_argument("--code", required=True)
    add("selftest", lambda args: selftest())
    return p


def main(argv=None):
    args = build().parse_args(argv)
    try:
        args.fn(args)
    except GiveUp as exc:
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
