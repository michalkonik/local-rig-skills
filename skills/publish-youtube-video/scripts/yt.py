#!/usr/bin/env python3
"""Upload a finished video project to YouTube with the official Data API v3 (your own channel, OAuth).

  yt.py setup-check                 is the OAuth client file there, is there a token
  yt.py auth-url                    print the Google consent URL (open it in any browser, approve)
  yt.py auth-code "PASTED_URL"      paste the address the browser ended on (http://127.0.0.1:8095/?code=...)
  yt.py meta SLUG                   create out/metadata.json (title, description with chapters, tags, flags)
  yt.py check SLUG                  validate metadata, video, thumbnail, captions -> OK or ERROR list
  yt.py upload SLUG [--dry-run]     upload (private or scheduled) + thumbnail + captions; resumable, idempotent

Files: ~/content/profile/youtube-client.json (OAuth "Desktop app" client from Google Cloud Console),
~/content/profile/youtube-token.json (written by auth-code, mode 600). Quota: insert ~100 units, captions 400,
thumbnail 50 of 10,000/day.
"""
import datetime, json, os, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request, uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import content  # noqa: E402

CLIENT = content.PROFILE / "youtube-client.json"
TOKEN = content.PROFILE / "youtube-token.json"
REDIRECT = "http://127.0.0.1:8095"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"


def die(msg, code=1):
    print("ERROR", msg)
    sys.exit(code)


def client():
    if not CLIENT.is_file():
        die(f"missing {CLIENT}: Google Cloud Console -> APIs & Services -> enable 'YouTube Data API v3' -> "
            "Credentials -> Create OAuth client ID -> Desktop app -> download JSON to that path", 3)
    c = json.loads(CLIENT.read_text())
    return c.get("installed") or c.get("web")


def post_form(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        die(f"{url}: {e.code} {e.read().decode()[:400]}", 4)


def access_token():
    if not TOKEN.is_file():
        die("not authorised yet: run yt.py auth-url, approve in a browser, then yt.py auth-code \"<address>\"", 4)
    t = json.loads(TOKEN.read_text())
    if t.get("expires_at", 0) - 60 > time.time():
        return t["access_token"]
    c = client()
    r = post_form(c["token_uri"], {"client_id": c["client_id"], "client_secret": c["client_secret"],
                                   "refresh_token": t["refresh_token"], "grant_type": "refresh_token"})
    t.update(access_token=r["access_token"], expires_at=time.time() + r.get("expires_in", 3600))
    save_token(t)
    return t["access_token"]


def save_token(t):
    TOKEN.write_text(json.dumps(t))
    os.chmod(TOKEN, 0o600)


def api(method, url, body=None, headers=None, raw=None):
    h = {"Authorization": f"Bearer {access_token()}", **(headers or {})}
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if body is not None and raw is None:
        h["Content-Type"] = "application/json; charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def proj(slug):
    d = content.VIDEOS / slug
    if not (d / "out" / "video.mp4").is_file():
        die(f"{d}/out/video.mp4 not found - build the video first", 3)
    return d


def meta(slug):
    d = proj(slug)
    f = d / "out" / "metadata.json"
    if f.exists():
        die(f"{f} exists - edit it", 2)
    sc = json.loads((d / "script.json").read_text())
    chapters = (d / "out" / "chapters.txt").read_text().strip() if (d / "out" / "chapters.txt").is_file() else ""
    desc = ["<2-3 lines: what the viewer gets, with the key number>", "",
            "<what was tested, on what hardware, which versions>", ""]
    if chapters:
        desc += ["Chapters:", chapters.replace("0:00", "00:00", 1), ""]
    desc += ["<links: repo with the commands, related video>"]
    m = {"title": sc.get("title", ""), "description": "\n".join(desc), "tags": [], "categoryId": "28",
         "defaultLanguage": "en", "privacyStatus": "private", "publishAt": "", "madeForKids": False,
         "containsSyntheticMedia": None, "thumbnail": "out/thumbnail.png", "captions": "out/captions.srt"}
    f.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"OK {f} - fill title/description/tags; set containsSyntheticMedia true/false (see SKILL.md)")


def check(slug, quiet=False):
    d = proj(slug)
    f = d / "out" / "metadata.json"
    if not f.is_file():
        die(f"no metadata - run yt.py meta {slug}", 3)
    m = json.loads(f.read_text())
    err = []
    if not 10 <= len(m["title"]) <= 100 or "<" in m["title"]:
        err.append(f"title must be 10-100 chars and filled ({len(m['title'])})")
    if "<" in m["description"] or len(m["description"].encode()) > 5000:
        err.append("description still has <placeholders> or is > 5000 bytes")
    if "<" in "".join(m["tags"]) or len(",".join(m["tags"])) > 480:
        err.append("tags: max ~480 chars total, no placeholders")
    if not isinstance(m.get("containsSyntheticMedia"), bool):
        err.append("containsSyntheticMedia must be true or false (decide with the rule in SKILL.md)")
    if m["privacyStatus"] not in ("private", "unlisted", "public"):
        err.append("privacyStatus must be private, unlisted or public")
    if m.get("publishAt"):
        try:
            at = datetime.datetime.fromisoformat(m["publishAt"].replace("Z", "+00:00"))
            if at <= datetime.datetime.now(datetime.timezone.utc):
                err.append("publishAt is in the past")
            if m["privacyStatus"] != "private":
                err.append("publishAt needs privacyStatus private")
        except ValueError:
            err.append("publishAt must be ISO 8601 UTC, e.g. 2026-11-05T15:00:00Z")
    ch = re.findall(r"(?m)^(\d+:\d\d(?::\d\d)?) ", m["description"])
    if ch and (ch[0] not in ("00:00", "0:00") or len(ch) < 3):
        err.append("chapters: first must be 00:00 and there must be >= 3")
    th = d / m["thumbnail"]
    if not th.is_file():
        err.append(f"thumbnail {th} missing (thumb.py)")
    elif th.stat().st_size > 2_000_000:
        err.append("thumbnail > 2 MB")
    for e in err:
        print("ERROR", e)
    if err:
        sys.exit(6)
    if not quiet:
        print(f"OK {slug}: '{m['title']}', {m['privacyStatus']}{' at ' + m['publishAt'] if m.get('publishAt') else ''}, "
              f"synthetic={m['containsSyntheticMedia']}, {len(ch)} chapters")
    return d, m


def upload(slug, dry):
    d, m = check(slug, quiet=True)
    state_f = d / "out" / "youtube.json"
    state = json.loads(state_f.read_text()) if state_f.is_file() else {}
    status = {"privacyStatus": m["privacyStatus"], "selfDeclaredMadeForKids": m["madeForKids"],
              "containsSyntheticMedia": m["containsSyntheticMedia"]}
    if m.get("publishAt"):
        status["publishAt"] = m["publishAt"]
    body = {"snippet": {"title": m["title"], "description": m["description"], "tags": m["tags"],
                        "categoryId": m["categoryId"], "defaultLanguage": m["defaultLanguage"],
                        "defaultAudioLanguage": m["defaultLanguage"]}, "status": status}
    if dry:
        print(json.dumps(body, indent=1, ensure_ascii=False)[:3000])
        print("DRY RUN - nothing uploaded")
        return
    video = d / "out" / "video.mp4"
    if not state.get("videoId"):
        size = video.stat().st_size
        s, h, b = api("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable"
                      "&part=snippet,status", body,
                      {"X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
        if s != 200:
            die(f"start upload: {s} {b.decode()[:500]}", 5)
        loc = h.get("Location") or h.get("location")
        with open(video, "rb") as fh:
            data = fh.read()
        for attempt in range(5):
            s, h, b = api("PUT", loc, raw=data, headers={"Content-Type": "video/mp4"})
            if s in (200, 201):
                break
            print(f"upload attempt {attempt + 1}: {s}, retrying", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
        else:
            die(f"upload failed: {s} {b.decode()[:500]}", 5)
        v = json.loads(b)
        state = {"videoId": v["id"], "uploaded": time.strftime("%Y-%m-%d %H:%M"),
                 "privacy": v["status"]["privacyStatus"], "uploadStatus": v["status"].get("uploadStatus")}
        state_f.write_text(json.dumps(state, indent=1))
    vid = state["videoId"]
    if not state.get("thumbnail"):
        th = d / m["thumbnail"]
        s, _, b = api("POST", f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                      raw=th.read_bytes(), headers={"Content-Type": "image/png"})
        state["thumbnail"] = "ok" if s == 200 else f"failed {s}: {b.decode()[:200]}"
    cap = d / m["captions"]
    if cap.is_file() and not state.get("captions"):
        bnd = uuid.uuid4().hex
        meta_part = json.dumps({"snippet": {"videoId": vid, "language": m["defaultLanguage"], "name": "English",
                                            "isDraft": False}})
        raw = (f"--{bnd}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta_part}\r\n"
               f"--{bnd}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + cap.read_bytes() + \
            f"\r\n--{bnd}--\r\n".encode()
        s, _, b = api("POST", "https://www.googleapis.com/upload/youtube/v3/captions?uploadType=multipart&part=snippet",
                      raw=raw, headers={"Content-Type": f"multipart/related; boundary={bnd}"})
        state["captions"] = "ok" if s == 200 else f"failed {s}: {b.decode()[:200]}"
    state_f.write_text(json.dumps(state, indent=1))
    print(f"OK uploaded https://youtu.be/{vid} ({state.get('privacy')}); thumbnail {state['thumbnail']}; "
          f"captions {state.get('captions', 'none')}")
    print(f"Studio: https://studio.youtube.com/video/{vid}/edit")


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else ""
    if cmd == "setup-check":
        client()
        print(f"OK client {CLIENT}; token: {'present' if TOKEN.is_file() else 'missing - run auth-url'}")
    elif cmd == "auth-url":
        c = client()
        q = {"client_id": c["client_id"], "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPES,
             "access_type": "offline", "prompt": "consent"}
        print("Open this in a browser, approve, then copy the address the browser ends on (the page will not load -"
              " that is expected) and run: yt.py auth-code \"<address>\"")
        print(c["auth_uri"] + "?" + urllib.parse.urlencode(q))
    elif cmd == "auth-code" and len(a) == 2:
        c = client()
        code = urllib.parse.parse_qs(urllib.parse.urlparse(a[1]).query).get("code", [a[1]])[0]
        r = post_form(c["token_uri"], {"code": code, "client_id": c["client_id"], "client_secret": c["client_secret"],
                                       "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
        if "refresh_token" not in r:
            die("no refresh token returned - run auth-url again (it asks for consent)", 4)
        save_token({**r, "expires_at": time.time() + r.get("expires_in", 3600)})
        print(f"OK token saved to {TOKEN} (mode 600)")
    elif cmd == "meta" and len(a) == 2:
        meta(a[1])
    elif cmd == "check" and len(a) == 2:
        check(a[1])
    elif cmd == "upload" and len(a) >= 2:
        upload(a[1], "--dry-run" in a)
    else:
        print(__doc__)
        sys.exit(0 if cmd in ("", "-h", "--help") else 2)


if __name__ == "__main__":
    main()
