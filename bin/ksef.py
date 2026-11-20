#!/usr/bin/env python3
"""List and download Firehorse KSeF invoices. Token comes from bw-secret."""
import argparse, base64, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

BASE = "https://api.ksef.mf.gov.pl/v2"
SUBJECTS = {"sales": "Subject1", "costs": "Subject2"}

def bw(ref):
    proc = subprocess.run(["bw-secret", ref], text=True, capture_output=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "bw-secret failed").strip().splitlines()
        print("ERROR vault", err[-1][:180] if err else "bw-secret failed")
        raise SystemExit(1)
    return proc.stdout.strip()

def session():
    s = requests.Session()
    s.trust_env = False
    s.headers["Accept"] = "application/json"
    return s

def authenticate(s):
    token = bw("ksef#token")
    nip = bw("ksef#nip")
    certs = s.get(f"{BASE}/security/public-key-certificates", timeout=30)
    if certs.status_code != 200:
        print("ERROR certs", certs.status_code)
        raise SystemExit(1)
    cer = next(c for c in certs.json() if "KsefTokenEncryption" in (c.get("usage") or []))
    pub = x509.load_der_x509_certificate(base64.b64decode(cer["certificate"])).public_key()
    challenge = s.post(f"{BASE}/auth/challenge", json={}, timeout=30)
    if challenge.status_code != 200:
        print("ERROR challenge", challenge.status_code)
        raise SystemExit(1)
    ch = challenge.json()
    plain = f"{token}|{ch['timestampMs']}".encode()
    encrypted = pub.encrypt(
        plain,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    init = s.post(f"{BASE}/auth/ksef-token", json={
        "challenge": ch["challenge"],
        "contextIdentifier": {"type": "Nip", "value": nip},
        "encryptedToken": base64.b64encode(encrypted).decode(),
    }, timeout=30)
    if init.status_code not in (200, 202):
        print("ERROR auth_init", init.status_code)
        raise SystemExit(1)
    body = init.json()
    ref = body["referenceNumber"]
    auth_tok = body["authenticationToken"]["token"]
    status = {}
    for _ in range(20):
        polled = s.get(f"{BASE}/auth/{ref}", headers={"Authorization": "Bearer " + auth_tok}, timeout=30)
        status = polled.json()
        code = (status.get("status") or {}).get("code")
        if code and code != 100:
            break
        time.sleep(1)
    if (status.get("status") or {}).get("code") != 200:
        print("ERROR auth_status", (status.get("status") or {}).get("code"))
        raise SystemExit(1)
    redeemed = s.post(f"{BASE}/auth/token/redeem", headers={"Authorization": "Bearer " + auth_tok}, timeout=30)
    if redeemed.status_code != 200:
        print("ERROR redeem", redeemed.status_code)
        raise SystemExit(1)
    return redeemed.json()["accessToken"]["token"], nip

def iso(day, end=False):
    clock = "23:59:59" if end else "00:00:00"
    return f"{day}T{clock}+00:00"

def query_all(s, access, subject, start, end, page_size):
    headers = {"Authorization": "Bearer " + access, "Content-Type": "application/json"}
    offset = 0
    rows = []
    while True:
        payload = {
            "subjectType": subject,
            "dateRange": {"dateType": "PermanentStorage", "from": iso(start), "to": iso(end, True)},
        }
        resp = None
        for attempt in range(3):
            resp = s.post(
                f"{BASE}/invoices/query/metadata",
                params={"pageOffset": offset, "pageSize": page_size},
                json=payload,
                headers=headers,
                timeout=60,
            )
            if resp.status_code == 429:
                time.sleep(2 + attempt * 3)
                continue
            break
        if resp.status_code != 200:
            print("ERROR query", subject, resp.status_code)
            raise SystemExit(1)
        data = resp.json()
        page = data.get("invoices") or data.get("invoiceHeaderList") or []
        rows.extend(page)
        if not data.get("hasMore") and len(page) < page_size:
            break
        if not page:
            break
        offset += len(page)
    return rows

def row_line(kind, inv):
    seller = inv.get("seller") or {}
    buyer = inv.get("buyer") or {}
    return "|".join([
        kind,
        str(inv.get("ksefNumber") or ""),
        str(inv.get("invoiceNumber") or ""),
        str(inv.get("issueDate") or ""),
        str(inv.get("grossAmount") or ""),
        str(inv.get("currency") or ""),
        str(seller.get("nip") or ""),
        str(seller.get("name") or "")[:60],
        str(buyer.get("nip") or ""),
        str(buyer.get("name") or "")[:60],
    ])

def chosen(subject):
    if subject == "both":
        return ["sales", "costs"]
    return [subject]

def collect(s, access, subject, start, end, page_size):
    found = []
    for kind in chosen(subject):
        for inv in query_all(s, access, SUBJECTS[kind], start, end, page_size):
            found.append((kind, inv))
    return found

def cmd_list(args):
    s = session()
    access, _nip = authenticate(s)
    found = collect(s, access, args.subject, args.date_from, args.date_to, args.page_size)
    print(f"OK list {len(found)}")
    for kind, inv in found:
        print(row_line(kind, inv))

def download_one(access, kind, number, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return "skipped"
    s = session()
    for attempt in range(3):
        resp = s.get(
            f"{BASE}/invoices/ksef/{number}",
            headers={"Authorization": "Bearer " + access, "Accept": "application/xml"},
            timeout=60,
        )
        if resp.status_code == 429:
            time.sleep(2 + attempt * 3)
            continue
        if resp.status_code != 200:
            print("ERROR download", kind, resp.status_code)
            return "failed"
        tmp = dest.with_suffix(".xml.part")
        tmp.write_bytes(resp.content)
        tmp.replace(dest)
        return "saved"
    print("ERROR download", kind, 429)
    return "failed"

def cmd_download(args):
    s = session()
    access, _nip = authenticate(s)
    found = collect(s, access, args.subject, args.date_from, args.date_to, args.page_size)
    out = Path(os.path.expanduser(args.out))
    saved = skipped = failed = 0
    jobs = []
    for kind, inv in found:
        number = inv.get("ksefNumber")
        if not number:
            failed += 1
            continue
        jobs.append((kind, number, out / kind / f"{number}.xml"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(download_one, access, kind, number, dest) for kind, number, dest in jobs]
        for fut in as_completed(futs):
            result = fut.result()
            if result == "saved":
                saved += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1
    print(f"OK download saved={saved} skipped={skipped} failed={failed} out={out}")
    if failed:
        raise SystemExit(1)

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("list", "download"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--from", dest="date_from", required=True)
        cmd.add_argument("--to", dest="date_to", required=True)
        cmd.add_argument("--subject", choices=("sales", "costs", "both"), default="both")
        cmd.add_argument("--page-size", type=int, default=100)
        if name == "download":
            cmd.add_argument("--out", default="~/Documents/ksef/6891205697")
    args = parser.parse_args()
    datetime.strptime(args.date_from, "%Y-%m-%d")
    datetime.strptime(args.date_to, "%Y-%m-%d")
    if args.page_size < 10 or args.page_size > 250:
        print("ERROR page_size must be 10..250")
        raise SystemExit(2)
    if args.cmd == "list":
        cmd_list(args)
    else:
        cmd_download(args)

if __name__ == "__main__":
    main()
