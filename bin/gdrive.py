#!/usr/bin/env python3
"""Google Drive for michal.konik.praca@gmail.com.

Token: ~/Documents/keep/gmail-tokens.json (scope drive) plus the OAuth client
JSON next to it. Never print either file. Creating files, tabs, cell writes,
batch updates, and trash do nothing unless --apply is set.
"""
import argparse, json, mimetypes, os, pathlib, sys, time, urllib.error, urllib.parse, urllib.request

DEFAULT_ACCOUNT = "michal.konik.praca@gmail.com"
KEEP = pathlib.Path.home() / "Documents" / "keep"
CLIENT = KEEP / "gmail-oauth-client.json"
TOKENS = KEEP / "gmail-tokens.json"
STATE = pathlib.Path.home() / ".local/state/rig-skills/gdrive"
API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
FOLDER = "application/vnd.google-apps.folder"
DOC = "application/vnd.google-apps.document"
SHEET = "application/vnd.google-apps.spreadsheet"
SLIDES = "application/vnd.google-apps.presentation"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
FIELDS = "id,name,mimeType,size,trashed"
MULTIPART_MAX = 5 * 1024 * 1024
CHUNK = 8 * 1024 * 1024
READ_CAP = 200_000
PREVIEW = 3500
LABEL = {FOLDER: "dir", DOC: "doc", SHEET: "sheet", SLIDES: "slides"}
EXPORTS = {
    DOC: {"docx": DOCX, "txt": "text/plain", "html": "text/html", "pdf": "application/pdf"},
    SHEET: {"xlsx": XLSX, "csv": "text/csv", "pdf": "application/pdf"},
    SLIDES: {"pptx": PPTX, "pdf": "application/pdf"},
}
DEFAULT_FMT = {DOC: "docx", SHEET: "xlsx", SLIDES: "pptx"}
EXT = {"docx": ".docx", "xlsx": ".xlsx", "pptx": ".pptx", "pdf": ".pdf", "csv": ".csv",
       "txt": ".txt", "html": ".html"}
SHEET_IN = {".xlsx": XLSX, ".xls": "application/vnd.ms-excel",
            ".ods": "application/vnd.oasis.opendocument.spreadsheet", ".csv": "text/csv"}
DOC_IN = {".docx": DOCX, ".doc": "application/msword", ".html": "text/html",
          ".htm": "text/html", ".txt": "text/plain", ".rtf": "application/rtf"}
SLIDES_IN = {".pptx": PPTX, ".ppt": "application/vnd.ms-powerpoint"}
TEXT_EXT = {".txt", ".md", ".json", ".csv", ".log", ".py", ".yaml", ".yml", ".xml", ".html"}


class GiveUp(SystemExit):
    pass


def say(text, code=1):
    print(text)
    raise GiveUp(code)


def escape_q(text):
    return text.replace("\\", "\\\\").replace("'", "\\'")


def is_file_id(text):
    return len(text) >= 25 and "/" not in text and " " not in text and all(c.isalnum() or c in "-_" for c in text)


def content_range(start, end, total):
    return f"bytes {start}-{end}/{total}"


def load_access(account):
    if not CLIENT.is_file() or not TOKENS.is_file():
        say("ERROR token: missing ~/Documents/keep/gmail-oauth-client.json or gmail-tokens.json.")
    client = json.loads(CLIENT.read_text())["installed"]
    saved = json.loads(TOKENS.read_text())
    row = saved.get(account)
    if not isinstance(row, dict) or not row.get("refresh_token"):
        known = ", ".join(sorted(k for k in saved if "@" in k))
        say(f"ERROR token: no refresh token for {account}. Known: {known}")
    scope = row.get("scope") or ""
    if "auth/drive" not in scope and "drive" not in scope.split():
        say(f"ERROR token: {account} has no Drive scope ({scope}). Re-consent before using gdrive.py.")
    form = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client.get("client_secret", ""),
        "refresh_token": row["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    tok = None
    for attempt in (1, 2):
        req = urllib.request.Request(client["token_uri"], data=form, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                tok = json.loads(res.read().decode())
            break
        except urllib.error.HTTPError as e:
            err = e.read().decode(errors="replace")[:180]
            if "invalid_grant" in err:
                say(f"ERROR token: refresh token for {account} is dead. Re-consent the Drive scope. Do not retry.")
            if e.code in (500, 503) and attempt == 1:
                time.sleep(1)
                continue
            say(f"ERROR token: refresh failed HTTP {e.code}.")
    if not tok or not tok.get("access_token"):
        say("ERROR token: refresh returned no access token.")
    return tok["access_token"]


def fail_http(status, raw, headers=None):
    msg = (raw or "")[:300].replace("\n", " ")
    try:
        err = json.loads(raw or "{}").get("error") or {}
        if isinstance(err, dict):
            msg = (err.get("message") or msg)[:300]
    except json.JSONDecodeError:
        pass
    if status == 401:
        say("ERROR 401: token rejected. Re-consent the Drive scope. Do not retry with the same token.")
    if status == 308:
        return 308, headers, b""
    extra = ""
    if "has not been used in project" in msg or "it is disabled" in msg:
        extra = " Do not overwrite the file with CSV."
    say(f"ERROR {status} {msg}.{extra}".rstrip("."))


def _http(method, url, data, headers, timeout):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.headers, res.read()
    except urllib.error.HTTPError as e:
        return fail_http(e.code, e.read().decode(errors="replace"), e.headers)


def api(method, url, query=None, body=None, content_type=None, raw=False, stream_to=None, timeout=120, token=None):
    token = token or load_access(ACCOUNT)
    qs = ("?" + urllib.parse.urlencode(query)) if query else ""
    headers = {"Authorization": "Bearer " + token}
    data = None
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
    if stream_to:
        req = urllib.request.Request(url + qs, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res, open(stream_to, "wb") as out:
                total = 0
                while True:
                    chunk = res.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    total += len(chunk)
            return {"bytes": total, "path": str(stream_to)}
        except urllib.error.HTTPError as e:
            pathlib.Path(stream_to).unlink(missing_ok=True)
            fail_http(e.code, e.read().decode(errors="replace"), e.headers)
    status, resp_headers, blob = _http(method, url + qs, data, headers, timeout)
    if raw:
        return blob
    if status == 308:
        return {"_status": 308, "_headers": resp_headers}
    if not blob:
        return {}
    if blob[:1] in (b"{", b"["):
        return json.loads(blob.decode())
    return {"_bytes": blob, "_headers": resp_headers}


def list_files(query, cap):
    rows, token = [], None
    while len(rows) < cap:
        q = {"q": query, "pageSize": str(min(100, cap - len(rows))),
             "fields": "nextPageToken,files(" + FIELDS + ")", "orderBy": "folder,name"}
        if token:
            q["pageToken"] = token
        data = api("GET", API + "/files", q)
        rows.extend(data.get("files") or [])
        token = data.get("nextPageToken")
        if not token:
            break
    return rows[:cap]


def get_file(file_id):
    return api("GET", API + "/files/" + urllib.parse.quote(file_id, safe=""),
               {"fields": FIELDS})


def resolve(item):
    item = (item or "").strip()
    if not item or item in (".", "/", "root"):
        return {"id": "root", "name": "root", "mimeType": FOLDER}
    if is_file_id(item):
        found = get_file(item)
        if found.get("trashed"):
            say(f"ERROR trashed: {found.get('name')} | {found.get('id')}")
        return found
    parent, cur = "root", {"id": "root", "name": "root", "mimeType": FOLDER}
    parts = [p for p in item.split("/") if p and p != "."]
    if not parts:
        say("ERROR empty path", 2)
    for i, part in enumerate(parts):
        rows = list_files(
            f"name = '{escape_q(part)}' and '{parent}' in parents and trashed = false", 10)
        if not rows:
            say(f"ERROR not found: {part}", 3)
        if len(rows) > 1:
            lines = "\n".join(f"- {label(r)} {r.get('name')} | {r.get('id')}" for r in rows)
            say(f"ERROR ambiguous '{part}'. Pass an id.\n{lines}", 3)
        cur = rows[0]
        if i < len(parts) - 1 and cur.get("mimeType") != FOLDER:
            say(f"ERROR not a folder: {part}", 3)
        parent = cur["id"]
    return cur


def label(row):
    return LABEL.get(row.get("mimeType"), "file")


def line(row):
    extra = f" | {row.get('size')} B" if row.get("size") else ""
    return f"- {label(row)} {row.get('name')}{extra} | {row.get('id')}"


def assert_safe(path):
    name = path.name.lower()
    if (name in {".env", "id_rsa", "id_ed25519", "credentials.json", "gmail-tokens.json",
                 "gmail-oauth-client.json"}
            or name.startswith(".env") or name.endswith((".pem", ".key"))
            or "token" in name or "secret" in name):
        say(f"ERROR refusing to upload a secret file: {path.name}")
    keep = KEEP.resolve()
    resolved = path.resolve()
    if resolved == keep or keep in resolved.parents:
        say("ERROR refusing to upload a file from ~/Documents/keep.")


def export_choice(mime, fmt):
    table = EXPORTS.get(mime)
    if not table:
        return None
    fmt = fmt or DEFAULT_FMT[mime]
    if fmt not in table:
        say(f"ERROR format {fmt} is not valid for this file. Use: {', '.join(sorted(table))}", 2)
    return table[fmt], fmt


def replacement(mime, suffix, force):
    suffix = suffix.lower()
    if mime == SHEET:
        if suffix not in SHEET_IN:
            return None, f"ERROR sheet replace wants .xlsx, .xls, .ods, or .csv, not {suffix or '(none)'}."
        if suffix == ".csv" and not force:
            return None, ("ERROR csv replace drops formulas. Re-run with --force only if values are enough, "
                          "or replace with .xlsx.")
        return (SHEET_IN[suffix], SHEET), None
    if mime == DOC:
        if suffix not in DOC_IN:
            return None, f"ERROR doc replace wants .docx, .html, .txt, .rtf, or .doc, not {suffix or '(none)'}."
        return (DOC_IN[suffix], DOC), None
    if mime == SLIDES:
        if suffix not in SLIDES_IN:
            return None, f"ERROR slides replace wants .pptx or .ppt, not {suffix or '(none)'}."
        return (SLIDES_IN[suffix], SLIDES), None
    guessed = mimetypes.guess_type("x" + suffix)[0] or "application/octet-stream"
    return (guessed, None), None


def safe_name(name):
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in name).strip()
    return (cleaned or "file")[:120]


def multipart(meta, content, content_type):
    boundary = "gdrive" + os.urandom(8).hex()
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + json.dumps(meta).encode()
        + f"\r\n--{boundary}\r\nContent-Type: {content_type}\r\n\r\n".encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, "multipart/related; boundary=" + boundary


def resumable(method, url, meta, path, content_type):
    token = load_access(ACCOUNT)
    total = path.stat().st_size
    status, headers, _ = _http(method, url, json.dumps(meta).encode(), {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": content_type,
        "X-Upload-Content-Length": str(total),
    }, 120)
    session = headers.get("Location")
    if not session:
        say("ERROR upload: no resumable session was returned.")
    start = 0
    with path.open("rb") as handle:
        while start < total:
            chunk = handle.read(CHUNK)
            end = start + len(chunk) - 1
            status, _, blob = _http("PUT", session, chunk, {
                "Authorization": "Bearer " + token,
                "Content-Type": content_type,
                "Content-Length": str(len(chunk)),
                "Content-Range": content_range(start, end, total),
            }, 300)
            if status == 308:
                got = headers.get("Range") if headers else None
                if got and got.startswith("bytes="):
                    start = int(got.split("-")[-1]) + 1
                else:
                    start = end + 1
                continue
            return json.loads(blob.decode() or "{}")
    say("ERROR upload: empty file.")


def send_file(method, url, meta, path, content_type):
    size = path.stat().st_size
    if size > MULTIPART_MAX:
        url = url.replace("uploadType=multipart", "uploadType=resumable")
        return resumable(method, url, meta, path, content_type)
    body, ctype = multipart(meta, path.read_bytes(), content_type)
    return api(method, url, body=body, content_type=ctype, timeout=180)


def cmd_about(_args):
    data = api("GET", API + "/about", {"fields": "user(emailAddress),storageQuota(limit,usage)"})
    user = (data.get("user") or {}).get("emailAddress")
    quota = data.get("storageQuota") or {}
    print(f"OK about {user} usage {quota.get('usage')} limit {quota.get('limit')}")


def cmd_list(args):
    folder = resolve(args.path)
    if folder.get("mimeType") != FOLDER:
        say(f"ERROR not a folder: {folder.get('name')}", 3)
    rows = list_files(f"'{folder['id']}' in parents and trashed = false", args.top)
    shown = args.path.strip("/") if args.path else ""
    print(f"OK list /{shown} {len(rows)}")
    print("\n".join(line(r) for r in rows) or "(empty)")


def cmd_search(args):
    words = [w for w in args.query if w.strip()]
    if not words:
        say("ERROR search needs words", 2)
    field = "fullText" if args.text else "name"
    query = " and ".join(f"{field} contains '{escape_q(w)}'" for w in words) + " and trashed = false"
    rows = list_files(query, args.top)
    print(f"OK search {len(rows)} q {' '.join(words)[:80]}")
    print("\n".join(line(r) for r in rows) or "(none)")


def preview(text, name):
    if len(text) <= PREVIEW:
        print(text)
        return
    STATE.mkdir(parents=True, exist_ok=True)
    path = STATE / safe_name(name)
    path.write_text(text)
    print(text[:1500])
    print(f"\nOK file {path} chars {len(text)}")


def cmd_read(args):
    item = resolve(args.item)
    print(f"OK stat {label(item)} {item.get('name')} | {item.get('size', 0)} B | {item.get('id')}")
    mime = item.get("mimeType")
    if mime == FOLDER:
        print("(folder, not a file)")
        return
    if mime == SHEET:
        blob = api("GET", API + "/files/" + urllib.parse.quote(item["id"], safe="") + "/export",
                   {"mimeType": "text/csv"}, raw=True)
        text = blob.decode("utf-8", "replace") if isinstance(blob, bytes) else ""
        print("WARN csv preview is values only. Formulas are not included. download the xlsx to edit.")
        preview(text, item["name"] + ".csv")
        return
    if mime == DOC:
        blob = api("GET", API + "/files/" + urllib.parse.quote(item["id"], safe="") + "/export",
                   {"mimeType": "text/plain"}, raw=True)
        preview(blob.decode("utf-8", "replace") if isinstance(blob, bytes) else "", item["name"] + ".txt")
        return
    suffix = pathlib.Path(item.get("name") or "").suffix.lower()
    text_mime = mime in {"text/plain", "text/csv", "text/html", "application/json"}
    if mime == SLIDES or (not text_mime and suffix not in TEXT_EXT):
        print(f"OK not text. Download it. mime {mime}")
        return
    size = int(item.get("size") or 0)
    if size > READ_CAP:
        print(f"OK not text. size {size}. Download it.")
        return
    blob = api("GET", API + "/files/" + urllib.parse.quote(item["id"], safe="") + "?alt=media", raw=True)
    preview(blob.decode("utf-8", "replace") if isinstance(blob, bytes) else "", item["name"])


def dest_path(item, fmt, out):
    base = safe_name(item.get("name") or item["id"])
    if fmt:
        suffix = EXT.get(fmt, "")
        if not base.lower().endswith(suffix):
            base += suffix
    target = pathlib.Path(out).expanduser() if out else STATE
    if out is None or target.is_dir() or str(out).endswith("/"):
        target.mkdir(parents=True, exist_ok=True)
        return target / base
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def cmd_download(args):
    item = resolve(args.item)
    if item.get("mimeType") == FOLDER:
        say("ERROR refusing to download a folder", 3)
    choice = export_choice(item.get("mimeType"), args.format)
    path = dest_path(item, choice[1] if choice else None, args.out)
    file_id = urllib.parse.quote(item["id"], safe="")
    if choice:
        api("GET", API + "/files/" + file_id + "/export", {"mimeType": choice[0]}, stream_to=path)
    else:
        if args.format:
            say("ERROR --format is only for a Google Doc, Sheet, or Slides file", 2)
        api("GET", API + "/files/" + file_id + "?alt=media", stream_to=path)
    print(f"OK download {path} bytes {path.stat().st_size} | {item.get('name')} | {item.get('id')}")


def parent_id(path):
    if not path or path in (".", "/", "root"):
        return "root"
    folder = resolve(path)
    if folder.get("mimeType") != FOLDER:
        say(f"ERROR parent is not a folder: {folder.get('name')}", 3)
    return folder["id"]


def cmd_mkdir(args):
    name = args.name.strip().strip("/")
    if not name or "/" in name:
        say("ERROR --name must be one folder name", 2)
    print(f"PLAN mkdir /{args.parent.strip('/')}/{name}".replace("//", "/"))
    if not args.apply:
        say("OK not sent. Re-run with --apply to create the folder.", 10)
    made = api("POST", API + "/files", body={
        "name": name, "mimeType": FOLDER, "parents": [parent_id(args.parent)]},
               query={"fields": FIELDS})
    print(f"OK mkdir {made.get('name')} | {made.get('id')}")


def cmd_upload(args):
    src = pathlib.Path(args.file).expanduser()
    if not src.is_file():
        say(f"ERROR file not found: {src}", 3)
    assert_safe(src)
    name = (args.name or src.name).strip().strip("/")
    if not name or "/" in name:
        say("ERROR --name must be a single file name", 2)
    print(f"PLAN upload {name} bytes {src.stat().st_size} -> /{args.parent.strip('/')}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to upload.", 10)
    meta = {"name": name, "parents": [parent_id(args.parent)]}
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    as_type = getattr(args, "as_type", None)
    if as_type:
        tables = {"sheet": (SHEET, SHEET_IN), "doc": (DOC, DOC_IN), "slides": (SLIDES, SLIDES_IN)}
        keep, table = tables[as_type]
        suffix = pathlib.Path(name).suffix.lower()
        if suffix not in table:
            say(f"ERROR --as {as_type} does not accept {suffix or '(none)'}. Use: {', '.join(sorted(table))}", 2)
        if as_type == "sheet" and suffix == ".csv" and not getattr(args, "force", False):
            say("ERROR csv upload as a Sheet drops formulas. Pass --force, or upload .xlsx.")
        ctype = table[suffix]
        meta["mimeType"] = keep
    made = send_file("POST", UPLOAD + "/files?uploadType=multipart&fields=" + FIELDS, meta, src, ctype)
    print(f"OK upload {made.get('name')} | {made.get('mimeType')} | {made.get('id')}")


def cmd_replace(args):
    src = pathlib.Path(args.file).expanduser()
    if not src.is_file():
        say(f"ERROR file not found: {src}", 3)
    assert_safe(src)
    print(f"PLAN replace {args.item} bytes {src.stat().st_size} file {src.name}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to replace.", 10)
    item = resolve(args.item)
    if item.get("mimeType") == FOLDER:
        say("ERROR refusing to replace a folder", 3)
    plan, err = replacement(item.get("mimeType"), src.suffix, args.force)
    if err:
        say(err)
    ctype, keep_mime = plan
    file_id = urllib.parse.quote(item["id"], safe="")
    if keep_mime:
        made = send_file("PATCH", UPLOAD + f"/files/{file_id}?uploadType=multipart&fields=" + FIELDS,
                         {"mimeType": keep_mime}, src, ctype)
    else:
        made = send_file("PATCH", UPLOAD + f"/files/{file_id}?uploadType=multipart&fields=" + FIELDS,
                         {}, src, ctype)
    print(f"OK replace {made.get('name') or item.get('name')} | {item.get('id')}")


def parse_values(args):
    if args.values:
        try:
            values = json.loads(args.values)
        except json.JSONDecodeError:
            say("ERROR --values must be JSON rows, for example [[\"a\",1],[\"b\",2]]", 2)
        if not isinstance(values, list) or any(not isinstance(row, list) for row in values):
            say("ERROR --values must be a list of lists", 2)
        return values
    if args.value is None:
        say("ERROR pass --value or --values", 2)
    return [[args.value]]


def cmd_sheet_get(args):
    item = resolve(args.item)
    if item.get("mimeType") != SHEET:
        say(f"ERROR not a Google Sheet: {item.get('name')}", 3)
    rng = urllib.parse.quote(args.range, safe="")
    data = api("GET", f"{SHEETS}/{item['id']}/values/{rng}")
    rows = data.get("values") or []
    print(f"OK sheet {item.get('name')} | {data.get('range')} | rows {len(rows)}")
    for row in rows[:30]:
        print("\t".join(str(cell) for cell in row))
    if len(rows) > 30:
        print(f"OK truncated showing 30 of {len(rows)}")


def cmd_sheet_set(args):
    values = parse_values(args)
    print(f"PLAN sheet-set {args.item} {args.range} rows {len(values)}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to write cells.", 10)
    item = resolve(args.item)
    if item.get("mimeType") != SHEET:
        say(f"ERROR not a Google Sheet: {item.get('name')}", 3)
    rng = urllib.parse.quote(args.range, safe="")
    data = api("PUT", f"{SHEETS}/{item['id']}/values/{rng}",
               query={"valueInputOption": "USER_ENTERED"},
               body={"range": args.range, "majorDimension": "ROWS", "values": values})
    print(f"OK sheet-set {item.get('name')} | {data.get('updatedRange')} | cells {data.get('updatedCells')}")


def require_sheet(item):
    found = resolve(item)
    if found.get("mimeType") != SHEET:
        say(f"ERROR not a Google Sheet: {found.get('name')}", 3)
    return found


def sheet_pages(item):
    data = api("GET", f"{SHEETS}/{item['id']}",
               {"fields": "spreadsheetId,properties.title,sheets.properties"})
    pages = [(row.get("properties") or {}) for row in data.get("sheets") or []]
    return data, pages


def find_tab(pages, name):
    hits = [page for page in pages if page.get("title") == name]
    if not hits:
        titles = ", ".join(page.get("title") or "?" for page in pages) or "(none)"
        say(f"ERROR no tab named {name}. Tabs: {titles}", 3)
    if len(hits) > 1:
        say(f"ERROR more than one tab named {name}", 3)
    return hits[0]


def refuse_only_tab(pages):
    if len(pages) <= 1:
        say("ERROR refusing to delete the only tab", 3)


def cmd_sheet_create(args):
    name = args.name.strip().strip("/")
    if not name or "/" in name:
        say("ERROR --name must be one spreadsheet name", 2)
    print(f"PLAN sheet-create {name}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to create the spreadsheet.", 10)
    made = api("POST", API + "/files", body={
        "name": name, "mimeType": SHEET, "parents": [parent_id(args.parent)]},
               query={"fields": FIELDS})
    print(f"OK sheet-create {made.get('name')} | {made.get('id')}")


def cmd_sheet_tabs(args):
    item = require_sheet(args.item)
    data, pages = sheet_pages(item)
    title = (data.get("properties") or {}).get("title") or item.get("name")
    print(f"OK tabs {title} | {item.get('id')} | {len(pages)}")
    for page in pages:
        print(f"- {page.get('index')} {page.get('title')} | {page.get('sheetId')}")


def cmd_sheet_add_tab(args):
    name = args.name.strip()
    if not name:
        say("ERROR --name is required", 2)
    print(f"PLAN sheet-add-tab {args.item} {name}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to add the tab.", 10)
    item = require_sheet(args.item)
    props = {"title": name}
    if args.index is not None:
        props["index"] = args.index
    api("POST", f"{SHEETS}/{item['id']}:batchUpdate",
        body={"requests": [{"addSheet": {"properties": props}}]})
    print(f"OK sheet-add-tab {item.get('name')} | {name}")


def cmd_sheet_rename_tab(args):
    print(f"PLAN sheet-rename-tab {args.item} {args.old} -> {args.new}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to rename the tab.", 10)
    item = require_sheet(args.item)
    _, pages = sheet_pages(item)
    tab = find_tab(pages, args.old)
    api("POST", f"{SHEETS}/{item['id']}:batchUpdate", body={"requests": [{
        "updateSheetProperties": {
            "properties": {"sheetId": tab.get("sheetId"), "title": args.new},
            "fields": "title",
        }
    }]})
    print(f"OK sheet-rename-tab {item.get('name')} | {args.old} -> {args.new}")


def cmd_sheet_delete_tab(args):
    print(f"PLAN sheet-delete-tab {args.item} {args.name}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to delete the tab.", 10)
    item = require_sheet(args.item)
    _, pages = sheet_pages(item)
    refuse_only_tab(pages)
    tab = find_tab(pages, args.name)
    api("POST", f"{SHEETS}/{item['id']}:batchUpdate",
        body={"requests": [{"deleteSheet": {"sheetId": tab.get("sheetId")}}]})
    print(f"OK sheet-delete-tab {item.get('name')} | {args.name}")


def cmd_sheet_append(args):
    values = parse_values(args)
    print(f"PLAN sheet-append {args.item} {args.range} rows {len(values)}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to append rows.", 10)
    item = require_sheet(args.item)
    rng = urllib.parse.quote(args.range, safe="")
    data = api("POST", f"{SHEETS}/{item['id']}/values/{rng}:append",
               query={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
               body={"range": args.range, "majorDimension": "ROWS", "values": values})
    updated = data.get("updates") or {}
    print(f"OK sheet-append {item.get('name')} | {updated.get('updatedRange')} | cells {updated.get('updatedCells')}")


def cmd_sheet_clear(args):
    print(f"PLAN sheet-clear {args.item} {args.range}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to clear the range.", 10)
    item = require_sheet(args.item)
    rng = urllib.parse.quote(args.range, safe="")
    api("POST", f"{SHEETS}/{item['id']}/values/{rng}:clear", body={})
    print(f"OK sheet-clear {item.get('name')} | {args.range}")


def load_requests(path):
    src = pathlib.Path(path).expanduser()
    if not src.is_file():
        say(f"ERROR file not found: {src}", 3)
    assert_safe(src)
    try:
        body = json.loads(src.read_text())
    except json.JSONDecodeError:
        say("ERROR --file must be JSON", 2)
    if isinstance(body, list):
        requests = body
    elif isinstance(body, dict) and isinstance(body.get("requests"), list):
        requests = body["requests"]
    else:
        say('ERROR JSON must be a list of requests or {"requests": [...]}', 2)
    if not requests:
        say("ERROR no requests in the file", 2)
    if any(not isinstance(row, dict) or len(row) != 1 for row in requests):
        say("ERROR each request must be one object with one operation", 2)
    return requests


def cmd_sheet_batch(args):
    requests = load_requests(args.file)
    kinds = ", ".join(next(iter(row)) for row in requests)
    print(f"PLAN sheet-batch {args.item} {len(requests)} {kinds}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to send the batch.", 10)
    item = require_sheet(args.item)
    api("POST", f"{SHEETS}/{item['id']}:batchUpdate", body={"requests": requests})
    print(f"OK sheet-batch {item.get('name')} | {item.get('id')} | requests {len(requests)}")


def cmd_trash(args):
    print(f"PLAN trash {args.item}")
    if not args.apply:
        say("OK not sent. Re-run with --apply to trash it.", 10)
    item = resolve(args.item)
    if item.get("id") == "root":
        say("ERROR refusing to trash My Drive")
    api("PATCH", API + "/files/" + urllib.parse.quote(item["id"], safe=""), body={"trashed": True})
    print(f"OK trashed {item.get('name')} | {item.get('id')}")


def selftest():
    assert escape_q("a'b") == "a\\'b"
    assert content_range(0, 3, 10) == "bytes 0-3/10"
    assert is_file_id("a" * 25)
    assert not is_file_id("short")
    assert not is_file_id("a" * 30 + "/x")
    assert export_choice(SHEET, None) == (XLSX, "xlsx")
    assert export_choice(DOC, "txt")[1] == "txt"
    assert replacement(SHEET, ".csv", False)[1].startswith("ERROR csv")
    assert replacement(SHEET, ".xlsx", False)[0] == (XLSX, SHEET)
    assert replacement(DOC, ".docx", False)[0][1] == DOC
    assert replacement("text/plain", ".txt", False)[0][1] is None
    calls = []

    def fake(method, url, query=None, body=None, content_type=None, raw=False, stream_to=None,
             timeout=120, token=None):
        calls.append((method, url))
        return {"id": "abc", "name": "n"}

    old = globals()["api"]
    globals()["api"] = fake
    old_out = sys.stdout
    try:
        sys.stdout = open(os.devnull, "w")
        try:
            cmd_upload(argparse.Namespace(file="/etc/hosts", parent="", name="n.txt", apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        assert calls == []
        try:
            cmd_replace(argparse.Namespace(file="/etc/hosts", item="abc", force=False, apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        assert calls == []
        try:
            cmd_sheet_set(argparse.Namespace(item="abc", range="A1", value="x", values=None, apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        assert calls == []
        try:
            cmd_sheet_create(argparse.Namespace(name="Book", parent="", apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        try:
            cmd_sheet_add_tab(argparse.Namespace(item="abc", name="Tab", index=None, apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        try:
            cmd_sheet_rename_tab(argparse.Namespace(item="abc", old="A", new="B", apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        try:
            cmd_sheet_delete_tab(argparse.Namespace(item="abc", name="A", apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        try:
            cmd_sheet_append(argparse.Namespace(item="abc", range="Tab!A1", value=None, values='[["a",1]]', apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        try:
            cmd_sheet_clear(argparse.Namespace(item="abc", range="Tab!A1:B2", apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        batch = pathlib.Path("/tmp/gdrive-sheet-batch-selftest.json")
        batch.write_text('[{"updateSheetProperties":{"properties":{"sheetId":1,"title":"B"},"fields":"title"}}]')
        try:
            cmd_sheet_batch(argparse.Namespace(item="abc", file=str(batch), apply=False))
        except GiveUp as exc:
            assert exc.code == 10
        batch.unlink(missing_ok=True)
        assert calls == []
        try:
            refuse_only_tab([{"title": "Only"}])
            raise AssertionError("only tab was deletable")
        except GiveUp as exc:
            assert exc.code == 3
        refuse_only_tab([{"title": "A"}, {"title": "B"}])
        try:
            cmd_upload(argparse.Namespace(file=str(TOKENS), parent="", name=None, apply=True))
            raise AssertionError("secret upload was allowed")
        except GiveUp as exc:
            assert exc.code == 1
        assert calls == []
    finally:
        sys.stdout.close()
        sys.stdout = old_out
        globals()["api"] = old
    print("OK selftest")


def build():
    p = argparse.ArgumentParser(
        prog="gdrive.py",
        description="Google Drive helper. Token stays in ~/Documents/keep. Writes need --apply.",
        epilog="examples: gdrive.py list | gdrive.py download ID --out ~/x.xlsx | gdrive.py replace ID --file ~/x.xlsx --apply")
    p.add_argument("--account", default=DEFAULT_ACCOUNT)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        return sp

    add("about", cmd_about)
    a = add("list", cmd_list)
    a.add_argument("path", nargs="?", default="")
    a.add_argument("--top", type=int, default=25)
    a = add("search", cmd_search)
    a.add_argument("query", nargs="+")
    a.add_argument("--top", type=int, default=15)
    a.add_argument("--text", action="store_true")
    a = add("read", cmd_read)
    a.add_argument("item")
    a = add("download", cmd_download)
    a.add_argument("item")
    a.add_argument("--out")
    a.add_argument("--format", choices=["docx", "xlsx", "pptx", "pdf", "csv", "txt", "html"])
    a = add("mkdir", cmd_mkdir)
    a.add_argument("--parent", default="")
    a.add_argument("--name", required=True)
    a.add_argument("--apply", action="store_true")
    a = add("upload", cmd_upload)
    a.add_argument("--parent", default="")
    a.add_argument("--file", required=True)
    a.add_argument("--name")
    a.add_argument("--as", dest="as_type", choices=["sheet", "doc", "slides"])
    a.add_argument("--force", action="store_true")
    a.add_argument("--apply", action="store_true")
    a = add("replace", cmd_replace)
    a.add_argument("item")
    a.add_argument("--file", required=True)
    a.add_argument("--force", action="store_true")
    a.add_argument("--apply", action="store_true")
    a = add("sheet-get", cmd_sheet_get)
    a.add_argument("item")
    a.add_argument("--range", required=True)
    a = add("sheet-set", cmd_sheet_set)
    a.add_argument("item")
    a.add_argument("--range", required=True)
    a.add_argument("--value")
    a.add_argument("--values")
    a.add_argument("--apply", action="store_true")
    a = add("sheet-create", cmd_sheet_create)
    a.add_argument("--name", required=True)
    a.add_argument("--parent", default="")
    a.add_argument("--apply", action="store_true")
    a = add("sheet-tabs", cmd_sheet_tabs)
    a.add_argument("item")
    a = add("sheet-add-tab", cmd_sheet_add_tab)
    a.add_argument("item")
    a.add_argument("--name", required=True)
    a.add_argument("--index", type=int)
    a.add_argument("--apply", action="store_true")
    a = add("sheet-rename-tab", cmd_sheet_rename_tab)
    a.add_argument("item")
    a.add_argument("--old", required=True)
    a.add_argument("--new", required=True)
    a.add_argument("--apply", action="store_true")
    a = add("sheet-delete-tab", cmd_sheet_delete_tab)
    a.add_argument("item")
    a.add_argument("--name", required=True)
    a.add_argument("--apply", action="store_true")
    a = add("sheet-append", cmd_sheet_append)
    a.add_argument("item")
    a.add_argument("--range", required=True)
    a.add_argument("--value")
    a.add_argument("--values")
    a.add_argument("--apply", action="store_true")
    a = add("sheet-clear", cmd_sheet_clear)
    a.add_argument("item")
    a.add_argument("--range", required=True)
    a.add_argument("--apply", action="store_true")
    a = add("sheet-batch", cmd_sheet_batch)
    a.add_argument("item")
    a.add_argument("--file", required=True)
    a.add_argument("--apply", action="store_true")
    a = add("trash", cmd_trash)
    a.add_argument("item")
    a.add_argument("--apply", action="store_true")
    add("selftest", lambda args: selftest())
    return p


def main(argv=None):
    global ACCOUNT
    args = build().parse_args(argv)
    ACCOUNT = args.account
    try:
        args.fn(args)
    except GiveUp as exc:
        sys.exit(exc.code if isinstance(exc.code, int) else 1)


if __name__ == "__main__":
    main()
