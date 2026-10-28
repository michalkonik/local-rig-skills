"""Shared helpers for the income skills (import with: sys.path.insert(0, <repo>/lib); import income).

Paths (override with env vars, e.g. for tests):
  INCOME_HOME   ~/income                         outputs the user reads (claims, gigs, promos, reviews)
  INCOME_DB     ~/.local/state/rig-skills/income.db   the SQLite ledger (lib/ledger.py)
  INCOME_CACHE  ~/.cache/rig-skills/income       fetched pages (6 h) and robots.txt (24 h)

fetch() is the only way these skills touch the web: real browser User-Agent, robots.txt respected,
>= 1.2 s between requests to the same host, pages cached 6 h, Cloudflare/login walls reported as Blocked.
"""
import datetime, hashlib, json, os, pathlib, re, time, unicodedata, urllib.error, urllib.parse, urllib.request
import urllib.robotparser

HOME = pathlib.Path.home()
INCOME = pathlib.Path(os.environ.get("INCOME_HOME", HOME / "income")).expanduser()
STATE = pathlib.Path(os.environ.get("RIG_STATE", HOME / ".local" / "state" / "rig-skills")).expanduser()
DB = pathlib.Path(os.environ.get("INCOME_DB", STATE / "income.db")).expanduser()
CACHE = pathlib.Path(os.environ.get("INCOME_CACHE", HOME / ".cache" / "rig-skills" / "income")).expanduser()
UA = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
MIN_GAP_S = 1.2
PAGE_TTL = 6 * 3600


class Blocked(Exception):
    """The site refused us (403/429/challenge/login). Degrade: ask the user to save the page by hand."""


def today():
    d = os.environ.get("INCOME_TODAY")          # tests can pin the date
    return datetime.date.fromisoformat(d) if d else datetime.date.today()


def slug(text, n=60):
    t = unicodedata.normalize("NFKD", str(text).replace("ł", "l").replace("Ł", "L"))
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.encode("ascii", "ignore").decode()).strip("-").lower()
    return t[:n].strip("-") or "item"


def _throttle(host):
    CACHE.mkdir(parents=True, exist_ok=True)
    stamp = CACHE / f".last-{host}"
    try:
        gap = time.time() - stamp.stat().st_mtime
        if gap < MIN_GAP_S:
            time.sleep(MIN_GAP_S - gap)
    except FileNotFoundError:
        pass
    stamp.touch()


def _get(url, timeout=40):
    host = urllib.parse.urlsplit(url).netloc
    _throttle(host)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pl,en;q=0.7",
                                               "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, body


def allowed(url):
    """robots.txt check (cached 24 h). Unknown robots -> allowed."""
    p = urllib.parse.urlsplit(url)
    robots = f"{p.scheme}://{p.netloc}/robots.txt"
    f = CACHE / f"robots-{p.netloc}.txt"
    if not f.exists() or time.time() - f.stat().st_mtime > 86400:
        code, body = _get(robots, timeout=20)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body if code == 200 else "")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(f.read_text().splitlines())
    return rp.can_fetch("*", url)


def fetch(url, ttl=PAGE_TTL):
    """Return page text (from cache if younger than ttl). Raise Blocked when the site refuses or robots.txt forbids."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if f.exists() and time.time() - f.stat().st_mtime < ttl:
        return f.read_text()
    if not allowed(url):
        raise Blocked(f"robots.txt of {urllib.parse.urlsplit(url).netloc} disallows {url}")
    code, body = _get(url)
    if code in (401, 403, 429, 503) or "challenges.cloudflare.com" in body[:20000] or "<title>Just a moment" in body[:3000]:
        raise Blocked(f"{url} answered HTTP {code} (bot challenge or login wall)")
    if code != 200:
        raise Blocked(f"{url} answered HTTP {code}")
    f.write_text(body)
    return body


def html_text(html):
    """Very small HTML -> text: drops scripts/styles, keeps line breaks at block ends."""
    import html as h
    t = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", html)
    t = re.sub(r"(?i)<(br|/p|/li|/h\d|/div|/tr|/section|/article)[^>]*>", "\n", t)
    t = h.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


# ------------------------------------------------------------------ money
def nbp_rate(code, day=None):
    """NBP table A mid rate from the last business day BEFORE `day` (art. 11a PIT act, the D-1 rule). Cached."""
    code = code.upper()
    if code == "PLN":
        return 1.0, "PLN"
    day = day or today()
    start, end = day - datetime.timedelta(days=10), day - datetime.timedelta(days=1)
    url = f"https://api.nbp.pl/api/exchangerates/rates/a/{code.lower()}/{start}/{end}/?format=json"
    try:
        data = json.loads(fetch(url, ttl=30 * 86400))
        r = data["rates"][-1]
        return float(r["mid"]), f"NBP {r['no']} ({r['effectiveDate']})"
    except Exception as e:  # offline or holiday gap: caller decides
        raise Blocked(f"NBP rate for {code} before {day} not available: {e}")


def write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_json(path, default):
    path = pathlib.Path(path)
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    return write(path, json.dumps(data, ensure_ascii=False, indent=1, default=str))
