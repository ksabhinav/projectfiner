"""Pure-logic tests for the harvester — no network, no disk beyond a tmp file.

    python3 audit/test_harvest.py
"""
import os, tempfile
import harvest as H


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_sha256():
    with tempfile.NamedTemporaryFile("wb", delete=False) as fh:
        fh.write(b"abc")
        p = fh.name
    try:
        check(H.sha256_file(p) ==
              "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "sha256 abc")
    finally:
        os.unlink(p)


def test_html_stub():
    check(H.looks_like_html_stub(b"tiny"), "short body is stub")
    check(H.looks_like_html_stub(b"   <!DOCTYPE html><html>...</html>" + b" " * 300), "html is stub")
    check(not H.looks_like_html_stub(b"%PDF-1.5" + b"\x00" * 4000), "real pdf is not stub")


def test_truncated():
    check(H.wayback_truncated({"warning": '299 archive.org "truncated by \\"length\\""'}), "warning header")
    check(H.wayback_truncated({"x-archive-orig-x-crawler-content-length": "5000000",
                               "content-length": "1048576"}), "orig > got")
    check(not H.wayback_truncated({"content-length": "1048576"}), "no truncation signal")


def test_wayback_raw_url():
    check(H.wayback_raw_url("20250815", "https://slbcap.nic.in/a.pdf") ==
          "https://web.archive.org/web/20250815id_/https://slbcap.nic.in/a.pdf", "id_ raw url")


def test_parse_cdx():
    text = ("20200101 https://x.in/a.pdf\n"
            "20250101 https://x.in/a.pdf\n"       # newer dup -> should win
            "20210101 https://x.in/b.pdf\n"
            "garbage line\n")
    out = dict((o, t) for t, o in H.parse_cdx(text))
    check(out["https://x.in/a.pdf"] == "20250101", "keeps latest snapshot")
    check(len(out) == 2, "dedup by original url")


def test_safe_filename():
    check(H.safe_filename("https://x.in/docs/CD Ratio 31.12.2025.xlsx?v=2") ==
          "CD_Ratio_31.12.2025.xlsx", "spaces+query stripped, ext kept")
    check(H.safe_filename("https://x.in/reports/") == "reports", "trailing slash -> last segment")
    check(H.safe_filename("https://slbcdelhi.pnb.bank.in") == "slbcdelhi.pnb.bank.in",
          "domain-only -> host as name")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
            n += 1
    print(f"\n{n} test groups passed")
