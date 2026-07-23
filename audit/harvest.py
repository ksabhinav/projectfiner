"""Source harvester — fetch + hash + manifest engine (Phase 1, artifact 1.5).

Reads audit/source_catalogue.csv, downloads the located sources into an archived
corpus, SHA-256 hashes each, and records provenance in audit/source_manifest.csv.
Built to run where network + disk allow (the ~3.8 GB corpus won't fit an
ephemeral session); safe to run repeatedly — it skips what it already has.

Design choices that matter for a verification corpus:
  * PDFs land in sources/<state>/ (gitignored); the manifest lives in audit/
    (tracked) so provenance survives without committing gigabytes.
  * Wayback truncates binaries >1 MB at capture time (gotcha #87) — detected via
    the `warning: 299 ... truncated by "length"` header and recorded as
    status=truncated so re-runs don't refetch a snapshot that can't improve.
  * Wayback serves a tiny HTML stub when a snapshot lacks the file — rejected.
  * Uses the `id_/` raw-content modifier so Wayback returns original bytes, not
    the wrapped viewer HTML.
  * Polite throttle (default 5 s/req; anon SPN/CDX ceiling ~15/min, gotcha #85).

Complements — does not replace — db/fetch_wayback_pdfs.py (bulk per-host CDX
walk). This one is catalogue-driven and manifest-first for the audit program.

    python3 audit/harvest.py --dry-run                 # plan only, no network
    python3 audit/harvest.py --states delhi,haryana    # fetch live portals
    python3 audit/harvest.py --wayback --states andhra-pradesh   # from Wayback CDX
    python3 audit/test_harvest.py                       # pure-logic tests, no network
"""
import csv, hashlib, os, re, ssl, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGUE = os.path.join(REPO, "audit", "source_catalogue.csv")
MANIFEST = os.path.join(REPO, "audit", "source_manifest.csv")
CORPUS = os.path.join(REPO, "sources")
UA = "FINER-integrity-harvester/1.0 (data audit; contact mail@projectfiner.com)"
BINARY_EXT = (".pdf", ".xlsx", ".xls", ".zip", ".rar", ".doc", ".docx", ".csv")

# ------------------------------------------------------------------- pure logic
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_html_stub(data):
    """Wayback returns a tiny HTML page when a snapshot has no real file body."""
    if len(data) < 256:
        return True
    head = data[:512].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def wayback_truncated(headers):
    """True if Wayback capped the capture (gotcha #87). `headers` is a dict-like
    of lowercased keys."""
    warn = str(headers.get("warning", "")).lower()
    if "truncated" in warn:
        return True
    orig = headers.get("x-archive-orig-x-crawler-content-length")
    got = headers.get("content-length")
    try:
        return bool(orig and got and int(orig) > int(got))
    except (TypeError, ValueError):
        return False


def wayback_raw_url(timestamp, original):
    """id_/ modifier -> raw original bytes rather than the viewer wrapper."""
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def cdx_pdf_query(host):
    return ("https://web.archive.org/cdx/search/cdx?"
            f"url={host}/*&matchType=prefix&filter=mimetype:application/pdf"
            "&collapse=urlkey&fl=timestamp,original&output=text&limit=100000")


def parse_cdx(text):
    """CDX 'timestamp original' lines -> [(ts, original)] keeping latest per url."""
    latest = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            ts, orig = parts[0], parts[1]
            if orig not in latest or ts > latest[orig]:
                latest[orig] = ts
    return sorted((ts, orig) for orig, ts in latest.items())


def safe_filename(url):
    """A filesystem-safe basename derived from a URL, keeping the extension."""
    base = re.sub(r"[?#].*$", "", url).rstrip("/").split("/")[-1] or "index"
    base = urllib.request.unquote(base)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_")
    return base[:150] or "index"


# ------------------------------------------------------------------ networking
def _ssl_ctx():
    ctx = ssl.create_default_context()
    for cand in (os.environ.get("SSL_CERT_FILE"), os.environ.get("REQUESTS_CA_BUNDLE"),
                 "/root/.ccr/ca-bundle.crt"):
        if cand and os.path.exists(cand):
            try:
                ctx.load_verify_locations(cand)
            except ssl.SSLError:
                pass
    return ctx


def http_get(url, timeout=60, retries=3, backoff=4.0):
    """(status, headers_lower, body_bytes). Retries with exponential backoff on
    transient failures. Honours HTTP(S)_PROXY from the environment."""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler(),                       # env proxies
        urllib.request.HTTPSHandler(context=_ssl_ctx()))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for attempt in range(retries):
        try:
            with opener.open(req, timeout=timeout) as r:
                body = r.read()
                headers = {k.lower(): v for k, v in r.headers.items()}
                return r.status, headers, body
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):                          # not transient
                return e.code, {}, b""
            last = e
        except Exception as e:                                # timeouts, conn refused
            last = e
        if attempt < retries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise last if last else RuntimeError("http_get failed")


def fetch_one(url, dest, delay=5.0):
    """Download one file to dest. Returns a status string:
    ok | truncated | stub | http_error | error. Skips if dest already present."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skip"
    try:
        status, headers, body = http_get(url)
    except Exception as e:
        return f"error:{type(e).__name__}"
    time.sleep(delay)
    if status in (404, 403):
        return f"http_{status}"
    if looks_like_html_stub(body):
        return "stub"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(body)
    return "truncated" if wayback_truncated(headers) else "ok"


# --------------------------------------------------------------------- harvest
def load_catalogue():
    if not os.path.exists(CATALOGUE):
        sys.exit("run build_source_catalogue.py first")
    with open(CATALOGUE, newline="") as fh:
        return list(csv.DictReader(fh))


def append_manifest(rows):
    new = not os.path.exists(MANIFEST)
    cols = ["state", "kind", "filename", "origin_url", "wayback_ts",
            "retrieved_at", "sha256", "bytes", "status"]
    with open(MANIFEST, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerows(rows)


def harvest(states=None, use_wayback=False, dry_run=False, limit=None, delay=5.0):
    rows = load_catalogue()
    if states:
        want = set(states)
        rows = [r for r in rows if r["state"] in want]

    # candidate direct files: catalogue URLs that already point at a binary
    direct = [r for r in rows if r["url_or_host"].lower().endswith(BINARY_EXT)]
    portals = [r for r in rows if r["kind"] in ("live_portal", "live_alias", "wayback_latest")]
    cdx_hosts = [r for r in rows if r["kind"] == "wayback_cdx_host"]

    plan = []
    for r in direct:
        plan.append(("direct", r["state"], r["url_or_host"], None))
    if use_wayback:
        for r in cdx_hosts:
            plan.append(("cdx", r["state"], r["url_or_host"], None))
    else:
        for r in portals:
            plan.append(("portal", r["state"], r["url_or_host"], None))

    print(f"Plan: {len(plan)} targets across {len({p[1] for p in plan})} states "
          f"({'WAYBACK' if use_wayback else 'live'} mode)")
    if dry_run:
        for mode, state, url, _ in plan[: (limit or 40)]:
            print(f"  [{mode:6}] {state:16} {url}")
        print("\n(dry run — no network, no writes)")
        return

    manifest_rows, done = [], 0
    for mode, state, url, _ in plan:
        if limit and done >= limit:
            break
        if mode == "cdx":                       # enumerate PDFs under the host
            try:
                _, _, body = http_get(cdx_pdf_query(url))
                time.sleep(delay)
                entries = parse_cdx(body.decode("utf-8", "replace"))
            except Exception as e:
                print(f"  CDX FAIL {state} {url}: {e}")
                continue
            print(f"  CDX {state} {url}: {len(entries)} archived PDFs")
            for ts, orig in entries:
                if limit and done >= limit:
                    break
                dest = os.path.join(CORPUS, state, f"{ts}_{safe_filename(orig)}")
                st = fetch_one(wayback_raw_url(ts, orig), dest, delay)
                done += 1
                _record(manifest_rows, state, "wayback_pdf", dest, orig, ts, st)
                print(f"    {st:10} {os.path.basename(dest)}")
        else:                                   # a single direct/portal URL
            dest = os.path.join(CORPUS, state, safe_filename(url))
            st = fetch_one(url, dest, delay)
            done += 1
            _record(manifest_rows, state, mode, dest, url, "", st)
            print(f"  {st:10} {state:16} {url}")

    if manifest_rows:
        append_manifest(manifest_rows)
        print(f"\nrecorded {len(manifest_rows)} rows -> {os.path.relpath(MANIFEST, REPO)}")


def _record(rows, state, kind, dest, url, ts, status):
    ok = status in ("ok", "truncated") and os.path.exists(dest)
    rows.append({
        "state": state, "kind": kind, "filename": os.path.relpath(dest, REPO),
        "origin_url": url, "wayback_ts": ts,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_file(dest) if ok else "",
        "bytes": os.path.getsize(dest) if ok else 0, "status": status,
    })


if __name__ == "__main__":
    a = sys.argv[1:]
    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default
    harvest(
        states=[s for s in (opt("--states", "") or "").split(",") if s] or None,
        use_wayback="--wayback" in a,
        dry_run="--dry-run" in a,
        limit=int(opt("--limit")) if opt("--limit") else None,
        delay=float(opt("--delay", "5")),
    )
