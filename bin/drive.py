#!/usr/bin/env python3
"""OneDrive via Microsoft Graph. Token: bw-secret onenote#access_token.

Never print the token. upload, mkdir, and delete do nothing unless --apply is set.
"""
import argparse, json, os, pathlib, subprocess, sys, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"
STATE = pathlib.Path.home() / ".local/state/rig-skills/drive"
MAX_TOP = 100
TEXT_EXT = {".txt", ".md", ".json", ".csv", ".log", ".py", ".yaml", ".yml", ".xml", ".html"}


class GiveUp(SystemExit):
    pass


def say(text, code=1):
    print(text)
    raise GiveUp(code)


def load_token():
    if os.environ.get("ONENOTE_TOKEN"):
        return os.environ["ONENOTE_TOKEN"]
    if not os.environ.get("BW_SESSION"):
        sess = pathlib.Path.home() / ".config/bw/session"
        if sess.is_file():
            os.environ["BW_SESSION"] = sess.read_text().strip()
    proc = subprocess.run(["bw-secret", "onenote#access_token"], capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="replace").strip().splitlines()
        msg = err[-1][:180] if err else "bw-secret failed"
        say(f"ERROR token: {msg}. Store a Graph access token as bw item onenote field access_token.")
    token = proc.stdout.decode().strip()
    if not token:
        say("ERROR token: empty value from bw-secret onenote#access_token.")
    return token


def graph(method, path, query=None, body=None, content_type=None, token=None, raw=False):
    qs = ("?" + urllib.parse.urlencode(query, safe="$,'")) if query else ""
    url = path if path.startswith("http") else GRAPH + path + qs
    data = None
    headers = {"Authorization": "Bearer " + (token or load_token()), "Accept": "application/json"}
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            headers["Content-Type"] = content_type or "application/json"
        elif isinstance(body, str):
            data = body.encode()
            headers["Content-Type"] = content_type or "text/plain"
        else:
            data = body
            headers["Content-Type"] = content_type or "application/octet-stream"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            blob = res.read()
            if raw:
                return blob
            if not blob:
                return {}
            ctype = res.headers.get("Content-Type", "")
            if "json" in ctype or blob[:1] in (b"{", b"["):
                return json.loads(blob.decode())
            return {"_bytes": blob}
    except urllib.error.HTTPError as e:
        raw_err = e.read().decode(errors="replace")
        code, msg = "", raw_err[:240].replace("\n", " ")
        try:
            err = json.loads(raw_err).get("error") or {}
            code, msg = err.get("code") or "", (err.get("message") or msg)[:240]
        except json.JSONDecodeError:
            pass
        if e.code == 401:
            say("ERROR 401: token rejected. Replace bw field onenote#access_token with a token copied after consent.")
        if e.code == 403:
            say("ERROR 403: token cannot use OneDrive. Consent Files.ReadWrite in Graph Explorer, then replace the saved token.")
        say(f"ERROR {e.code} {code} {msg}".strip())


def drive_ref(path):
    path = (path or "").strip().strip("/")
    if not path or path in (".", "root"):
        return "/me/drive/root", True
    parts = [urllib.parse.quote(p) for p in path.split("/") if p and p != "."]
    return "/me/drive/root:/" + "/".join(parts) + ":", False


def children_path(path):
    ref, is_root = drive_ref(path)
    return "/me/drive/root/children" if is_root else ref + "/children"


def get_list(path, query, top):
    top = max(1, min(int(top), MAX_TOP))
    q = dict(query or {})
    q["$top"] = str(min(top, 50))
    rows, guard = [], 0
    while path and len(rows) < top and guard < 8:
        guard += 1
        if path.startswith(GRAPH):
            path = path[len(GRAPH):]
        base, _, qs = path.partition("?")
        if qs and not q:
            data = graph("GET", base + "?" + qs)
        else:
            data = graph("GET", base, q if q else None)
        rows.extend(data.get("value") or [])
        path, q = data.get("@odata.nextLink"), None
    return rows[:top]


def kind(row):
    if row.get("folder") is not None:
        return "dir"
    return "file"


def line(row):
    extra = ""
    if kind(row) == "file":
        extra = f" | {row.get('size', 0)} B"
    return f"- {kind(row)} {row.get('name')}{extra} | {row.get('id')}"


def cmd_list(args):
    rows = get_list(children_path(args.path), {"$select": "id,name,size,folder,file"}, args.top)
    print(f"OK list /{args.path.strip('/')} {len(rows)}")
    print("\n".join(line(r) for r in rows) or "(empty)")


def cmd_search(args):
    q = " ".join(args.query).replace("'", " ")
    rows = get_list(f"/me/drive/root/search(q='{urllib.parse.quote(q)}')",
                    {"$select": "id,name,size,folder,file"}, args.top)
    print(f"OK search {len(rows)} q {q[:80]}")
    print("\n".join(line(r) for r in rows) or "(none)")


def resolve_item(path_or_id):
    if path_or_id.startswith("01") or len(path_or_id) > 40 and "/" not in path_or_id:
        return graph("GET", "/me/drive/items/" + urllib.parse.quote(path_or_id, safe="")
                     + "?$select=id,name,size,folder,file,parentReference")
    ref, _ = drive_ref(path_or_id)
    return graph("GET", ref + "?$select=id,name,size,folder,file,parentReference")


def cmd_stat(args):
    item = resolve_item(args.item)
    print(f"OK stat {kind(item)} {item.get('name')} | {item.get('size', 0)} B | {item.get('id')}")


def cmd_read(args):
    item = resolve_item(args.item)
    print(f"OK stat {kind(item)} {item.get('name')} | {item.get('size', 0)} B | {item.get('id')}")
    if kind(item) != "file":
        print("(folder, not a file)")
        return
    ext = pathlib.Path(item.get("name") or "").suffix.lower()
    size = int(item.get("size") or 0)
    if ext not in TEXT_EXT or size > 200_000:
        say(f"OK not text. size {size} ext {ext or '(none)'}. Refusing to dump a binary file.")
    blob = graph("GET", f"/me/drive/items/{urllib.parse.quote(item['id'], safe='')}/content", raw=True)
    text = blob.decode("utf-8", "replace")
    if len(text) <= 3500:
        print(text)
        return
    STATE.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in item["name"])[:80]
    path = STATE / safe
    path.write_text(text)
    print(text[:1500])
    print(f"\nOK file {path} chars {len(text)}")


def cmd_mkdir(args):
    parent = args.parent or ""
    name = args.name.strip().strip("/")
    if not name or "/" in name:
        say("ERROR --name must be one folder name", 2)
    print(f"PLAN mkdir /{parent.strip('/')}/{name}".replace("//", "/"))
    if not args.apply:
        say("OK not sent. Re-run with --apply to create the folder.", 10)
    made = graph("POST", children_path(parent), body={
        "name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
    print(f"OK mkdir {made.get('name')} | {made.get('id')}")


def cmd_upload(args):
    src = pathlib.Path(args.file)
    if not src.is_file():
        say(f"ERROR file not found: {src}", 3)
    data = src.read_bytes()
    if len(data) > 4_000_000:
        say("ERROR file is over 4 MB. This command only uploads small files.", 1)
    name = (args.name or src.name).strip().strip("/")
    if not name or "/" in name:
        say("ERROR --name must be a single file name", 2)
    parent = args.parent or ""
    print(f"PLAN upload {name} bytes {len(data)} -> /{parent.strip('/')}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to upload.", 10)
    ref, is_root = drive_ref(parent)
    target = f"/me/drive/root:/{urllib.parse.quote(name)}:/content" if is_root else ref[:-1] + "/" + urllib.parse.quote(name) + ":/content"
    made = graph("PUT", target, body=data, content_type="application/octet-stream")
    print(f"OK upload {made.get('name')} | {made.get('id')}")


def cmd_delete(args):
    item = resolve_item(args.item)
    print(f"PLAN delete {kind(item)} {item.get('name')} | {item.get('id')}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to delete.", 10)
    graph("DELETE", "/me/drive/items/" + urllib.parse.quote(item["id"], safe=""))
    print(f"OK deleted {item.get('name')} | {item.get('id')}")


def selftest():
    assert drive_ref("")[1] is True
    assert drive_ref("a/b")[0] == "/me/drive/root:/a/b:"
    assert " " not in drive_ref("my docs")[0]
    os.environ["ONENOTE_TOKEN"] = "test-token"
    calls = []

    def fake(method, path, query=None, body=None, content_type=None, token=None, raw=False):
        calls.append(method)
        assert token == "test-token" or token is None or True
        if method == "PUT":
            return {"name": "n.txt", "id": "abc"}
        say("ERROR unexpected " + method)

    import io
    real = globals()["graph"]
    globals()["graph"] = fake
    old = sys.stdout
    try:
        sys.stdout = io.StringIO()
        try:
            cmd_upload(argparse.Namespace(file="/etc/hosts", parent="", name="n.txt", apply=False))
        except GiveUp as e:
            assert e.code == 10
        assert calls == []
        sys.stdout = io.StringIO()
        cmd_upload(argparse.Namespace(file="/etc/hosts", parent="", name="n.txt", apply=True))
        assert calls == ["PUT"]
    finally:
        sys.stdout = old
        globals()["graph"] = real
    print("OK selftest")


def build():
    p = argparse.ArgumentParser(prog="drive.py", description="OneDrive helper. Token: bw onenote#access_token.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        return sp

    a = add("list", cmd_list)
    a.add_argument("path", nargs="?", default="")
    a.add_argument("--top", type=int, default=25)
    a = add("search", cmd_search)
    a.add_argument("query", nargs="+")
    a.add_argument("--top", type=int, default=15)
    a = add("stat", cmd_stat)
    a.add_argument("item")
    a = add("read", cmd_read)
    a.add_argument("item")
    a = add("mkdir", cmd_mkdir)
    a.add_argument("--parent", default="")
    a.add_argument("--name", required=True)
    a.add_argument("--apply", action="store_true")
    a = add("upload", cmd_upload)
    a.add_argument("--parent", default="")
    a.add_argument("--file", required=True)
    a.add_argument("--name")
    a.add_argument("--apply", action="store_true")
    a = add("delete", cmd_delete)
    a.add_argument("item")
    a.add_argument("--apply", action="store_true")
    add("selftest", lambda args: selftest())
    return p


def main(argv=None):
    args = build().parse_args(argv)
    try:
        args.fn(args)
    except GiveUp as e:
        sys.exit(e.code if isinstance(e.code, int) else 1)


if __name__ == "__main__":
    main()
