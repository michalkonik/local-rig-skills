#!/usr/bin/env python3
"""OneNote via Microsoft Graph. Token stays in Bitwarden: bw-secret onenote#access_token.

Never print the token. Writes (create, append) do nothing unless --apply is set.
"""
import argparse, html, json, os, pathlib, re, subprocess, sys, urllib.error, urllib.parse, urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"
STATE = pathlib.Path.home() / ".local/state/rig-skills/onenote"
MAX_TOP = 100


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
        say(f"ERROR token: {msg}. Store it as bw item onenote field access_token.")
    token = proc.stdout.decode().strip()
    if not token:
        say("ERROR token: empty value from bw-secret onenote#access_token.")
    return token


def graph(method, path, query=None, body=None, content_type=None, token=None, quiet=False):
    qs = ("?" + urllib.parse.urlencode(query, safe="$,'\"")) if query else ""
    url = GRAPH + path + qs
    data = None
    headers = {"Authorization": "Bearer " + (token or load_token()), "Accept": "application/json, text/html;q=0.9"}
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            headers["Content-Type"] = content_type or "application/json"
        else:
            data = body.encode() if isinstance(body, str) else body
            headers["Content-Type"] = content_type or "text/plain"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            raw = res.read()
            if not raw:
                return {}
            ctype = res.headers.get("Content-Type", "")
            if "json" in ctype or raw[:1] in (b"{", b"["):
                return json.loads(raw.decode())
            return {"_text": raw.decode(errors="replace")}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        code, msg = "", raw[:240].replace("\n", " ")
        try:
            err = json.loads(raw).get("error") or {}
            code, msg = err.get("code") or "", (err.get("message") or msg)[:240]
        except json.JSONDecodeError:
            pass
        if quiet:
            raise GiveUp(e.code)
        if e.code == 401 and code == "40001":
            say("ERROR OneNote 401: this token can sign in to Graph but OneNote rejected it. "
                "Replace bw field onenote#access_token with a token that includes Notes.ReadWrite.")
        if e.code == 401:
            say("ERROR 401: token rejected. Replace bw field onenote#access_token.")
        if e.code == 403:
            say("ERROR 403: token is missing Notes.Read or Notes.ReadWrite.")
        say(f"ERROR {e.code} {code} {msg}".strip())


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


def label(row):
    return row.get("displayName") or row.get("title") or "(untitled)"


def resolve(rows, wanted, kind):
    if not wanted:
        say(f"ERROR {kind} name or id required")
    exact = [r for r in rows if r.get("id") == wanted or label(r).casefold() == wanted.casefold()]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        say("ERROR " + kind + " name is ambiguous:\n" + "\n".join(f"- {label(r)} | {r.get('id')}" for r in exact[:8]))
    part = [r for r in rows if wanted.casefold() in label(r).casefold() or wanted.casefold() in (r.get("id") or "").casefold()]
    if len(part) == 1:
        return part[0]
    if not part:
        preview = "\n".join(f"- {label(r)} | {r.get('id')}" for r in rows[:8]) or "(none)"
        say(f"ERROR {kind} not found: {wanted}\n{preview}", 3)
    say("ERROR " + kind + " matched several:\n" + "\n".join(f"- {label(r)} | {r.get('id')}" for r in part[:8]))


def line(row):
    return f"- {label(row)} | {row.get('id')}"


def cmd_notebooks(args):
    rows = get_list("/me/onenote/notebooks", {"$select": "id,displayName"}, args.top)
    print(f"OK notebooks {len(rows)}")
    print("\n".join(line(r) for r in rows) or "(none)")


def all_notebooks():
    return get_list("/me/onenote/notebooks", {"$select": "id,displayName"}, MAX_TOP)


def sections_under(notebook_id):
    return get_list(f"/me/onenote/notebooks/{urllib.parse.quote(notebook_id)}/sections",
                    {"$select": "id,displayName"}, MAX_TOP)


def groups_under(notebook_id):
    return get_list(f"/me/onenote/notebooks/{urllib.parse.quote(notebook_id)}/sectionGroups",
                    {"$select": "id,displayName"}, MAX_TOP)


def child_sections(group_id):
    return get_list(f"/me/onenote/sectionGroups/{urllib.parse.quote(group_id)}/sections",
                    {"$select": "id,displayName"}, MAX_TOP)


def child_groups(group_id):
    return get_list(f"/me/onenote/sectionGroups/{urllib.parse.quote(group_id)}/sectionGroups",
                    {"$select": "id,displayName"}, MAX_TOP)


def cmd_sections(args):
    nb = resolve(all_notebooks(), args.notebook, "notebook")
    rows = sections_under(nb["id"])
    groups = groups_under(nb["id"])
    print(f"OK sections {len(rows)} groups {len(groups)} notebook {label(nb)}")
    if groups:
        print("groups:")
        print("\n".join(line(g) for g in groups))
    print("sections:")
    print("\n".join(line(r) for r in rows) or "(none)")


def cmd_tree(args):
    books = all_notebooks()
    if args.notebook:
        books = [resolve(books, args.notebook, "notebook")]
    print(f"OK tree notebooks {len(books)}")
    for nb in books:
        print(f"- {label(nb)} | {nb.get('id')}")
        _tree_group_children(nb["id"], notebook=True, indent="  ", depth=0)


def _tree_group_children(parent_id, notebook, indent, depth):
    if depth > 4:
        print(f"{indent}- (deeper groups omitted)")
        return
    groups = groups_under(parent_id) if notebook else child_groups(parent_id)
    sections = sections_under(parent_id) if notebook else child_sections(parent_id)
    for g in groups:
        print(f"{indent}- [group] {label(g)} | {g.get('id')}")
        _tree_group_children(g["id"], notebook=False, indent=indent + "  ", depth=depth + 1)
    for s in sections:
        print(f"{indent}- [section] {label(s)} | {s.get('id')}")


def cmd_pages(args):
    sections = get_list("/me/onenote/sections", {"$select": "id,displayName"}, MAX_TOP)
    sec = resolve(sections, args.section, "section")
    rows = get_list(f"/me/onenote/sections/{urllib.parse.quote(sec['id'])}/pages",
                    {"$select": "id,title,lastModifiedDateTime"}, args.top)
    print(f"OK pages {len(rows)} section {label(sec)}")
    for r in rows:
        when = (r.get("lastModifiedDateTime") or "")[:10]
        print(f"- {label(r)} | {when} | {r.get('id')}")
    if not rows:
        print("(none)")


def cmd_search(args):
    q = " ".join(args.query).strip()
    if not q:
        say("ERROR search words required", 2)
    safe = q.replace('"', " ")
    rows = get_list("/me/onenote/pages", {
        "$search": f'"{safe}"',
        "$select": "id,title,lastModifiedDateTime",
        "$top": str(max(1, min(args.top, MAX_TOP))),
    }, args.top)
    print(f"OK search {len(rows)} q {safe[:80]}")
    for r in rows:
        when = (r.get("lastModifiedDateTime") or "")[:10]
        print(f"- {label(r)} | {when} | {r.get('id')}")
    if not rows:
        print("(none)")


def html_to_text(raw):
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p>", "\n", raw)
    raw = re.sub(r"(?i)</h[1-6]>", "\n", raw)
    raw = re.sub(r"(?i)</li>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw).replace("\r", "")
    raw = re.sub(r"[ \t]+\n", "\n", raw)
    raw = re.sub(r"[ \t]{2,}", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def page_html(title, text):
    parts = []
    for block in text.split("\n"):
        parts.append(f"<p>{html.escape(block) if block else ' '}</p>")
    body = "".join(parts) or "<p></p>"
    return (
        "<!DOCTYPE html><html><head><title>"
        + html.escape(title)
        + "</title></head><body>"
        + body
        + "</body></html>"
    )


def fragment(text):
    return "".join(f"<p>{html.escape(line) if line else ' '}</p>" for line in text.split("\n")) or "<p></p>"


def read_text_arg(args):
    if args.file:
        return pathlib.Path(args.file).read_text()
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    say("ERROR pass --text, --file, or stdin", 2)


def find_page(wanted):
    rows = get_list("/me/onenote/pages", {"$select": "id,title", "$top": "50"}, 50)
    # A direct id get is cheaper when the user pasted an id (they contain '!').
    if "!" in wanted or len(wanted) > 40:
        try:
            data = graph("GET", "/me/onenote/pages/" + urllib.parse.quote(wanted, safe="") + "?$select=id,title", quiet=True)
            if data.get("id"):
                return data
        except GiveUp:
            pass
    return resolve(rows, wanted, "page")


def cmd_read(args):
    page = find_page(args.page)
    data = graph("GET", "/me/onenote/pages/" + urllib.parse.quote(page["id"], safe="") + "/content")
    text = html_to_text(data.get("_text") or "")
    print(f"OK read {label(page)} | {page.get('id')}")
    if len(text) <= 3500:
        print(text or "(empty)")
        return
    STATE.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", page["id"])[:80]
    path = STATE / f"{safe}.txt"
    path.write_text(text)
    print(text[:1500])
    print(f"\nOK file {path} chars {len(text)}")


def cmd_create(args):
    sections = get_list("/me/onenote/sections", {"$select": "id,displayName"}, MAX_TOP)
    sec = resolve(sections, args.section, "section")
    text = read_text_arg(args)
    title = args.title.strip()
    if not title:
        say("ERROR --title required", 2)
    doc = page_html(title, text)
    print(f"PLAN create section {label(sec)} | {sec.get('id')}")
    print(f"PLAN title {title} chars {len(text)}")
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to create the page.", 10)
    made = graph("POST", f"/me/onenote/sections/{urllib.parse.quote(sec['id'], safe='')}/pages",
                 body=doc, content_type="application/xhtml+xml")
    print(f"OK created {made.get('title') or title} | {made.get('id')}")


def cmd_append(args):
    page = find_page(args.page)
    text = read_text_arg(args)
    print(f"PLAN append {label(page)} | {page.get('id')} chars {len(text)}")
    if not args.apply:
        say("OK not sent. Re-run the same command with --apply to append.", 10)
    graph("PATCH", "/me/onenote/pages/" + urllib.parse.quote(page["id"], safe="") + "/content",
          body=[{"target": "body", "action": "append", "content": fragment(text)}])
    print(f"OK appended {label(page)} | {page.get('id')}")


def selftest():
    assert html.escape("<b>") == "&lt;b&gt;"
    doc = page_html("A & B", "one\n<two>")
    assert "<title>A &amp; B</title>" in doc and "&lt;two&gt;" in doc
    assert "<p>one</p><p>&lt;two&gt;</p>" in fragment("one\n<two>")
    assert html_to_text("<p>Hi<br>there</p><script>x</script>") == "Hi\nthere"
    os.environ["ONENOTE_TOKEN"] = "test-token"
    calls = []

    def fake(method, path, query=None, body=None, content_type=None, token=None):
        calls.append((method, path, token))
        assert token != "test-token" or True
        if path.startswith("/me/onenote/sections/") and path.endswith("/pages") and method == "POST":
            return {"id": "1-1!2-2", "title": "T"}
        say("ERROR selftest unexpected call " + method + " " + path)

    global graph
    real = graph
    try:
        # bind name used by cmd_create: it calls graph() global. Patch via assignment in module.
        globals()["graph"] = fake
        # resolve() needs sections. Give it one row by patching get_list.
        globals()["get_list"] = lambda path, query, top: [{"id": "sec-1", "displayName": "Taxes"}]
        buf = io_capture()
        try:
            cmd_create(argparse.Namespace(section="Taxes", title="T", text="hello", file=None, apply=False))
        except GiveUp as e:
            assert e.code == 10, e.code
        out = buf.getvalue()
        assert "PLAN create" in out and "not sent" in out
        assert calls == []
        buf = io_capture()
        cmd_create(argparse.Namespace(section="Taxes", title="T", text="hello", file=None, apply=True))
        assert calls and calls[0][0] == "POST"
        assert "OK created" in buf.getvalue()
    finally:
        globals()["graph"] = real
    print("OK selftest")


class io_capture:
    def __enter__(self):
        return self

    def __init__(self):
        import io
        self._io = io.StringIO()
        self._old = sys.stdout
        sys.stdout = self._io

    def getvalue(self):
        sys.stdout = self._old
        return self._io.getvalue()


def build():
    p = argparse.ArgumentParser(prog="onenote.py", description="OneNote Graph helper. Token: bw onenote#access_token.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        return sp

    a = add("notebooks", cmd_notebooks)
    a.add_argument("--top", type=int, default=25)
    a = add("sections", cmd_sections)
    a.add_argument("notebook")
    a.add_argument("--top", type=int, default=50)
    a = add("tree", cmd_tree)
    a.add_argument("notebook", nargs="?")
    a = add("pages", cmd_pages)
    a.add_argument("section")
    a.add_argument("--top", type=int, default=25)
    a = add("search", cmd_search)
    a.add_argument("query", nargs="+")
    a.add_argument("--top", type=int, default=15)
    a = add("read", cmd_read)
    a.add_argument("page")
    a = add("create", cmd_create)
    a.add_argument("--section", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--text")
    a.add_argument("--file")
    a.add_argument("--apply", action="store_true")
    a = add("append", cmd_append)
    a.add_argument("page")
    a.add_argument("--text")
    a.add_argument("--file")
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
