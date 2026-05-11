#!/usr/bin/env python3
"""Download all Gujarat SLBC ZIP archives listed in meetings_audit.txt
and unzip them into data-tables/<meeting_num>/. Skips cached files.
"""
import os
import sys
import urllib.request
import urllib.parse
import zipfile
import ssl
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(BASE, "meetings_audit.txt")
DOWNLOADS = os.path.join(BASE, "downloads")
DATA_TABLES = os.path.join(BASE, "data-tables")

os.makedirs(DOWNLOADS, exist_ok=True)
os.makedirs(DATA_TABLES, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def parse_audit():
    rows = []
    with open(AUDIT) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                rows.append({
                    "meeting": int(parts[0]),
                    "quarter": parts[1],
                    "period": parts[2],
                    "date": parts[3],
                    "url": parts[4],
                })
    return rows


def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return False  # cached
    # URL-encode spaces
    safe_url = urllib.parse.quote(url, safe=":/?&=%")
    req = urllib.request.Request(safe_url, headers={
        "User-Agent": "Mozilla/5.0 (FINER data pipeline)"
    })
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return None


def unzip_to(zip_path, target_dir):
    if os.path.isdir(target_dir) and len(os.listdir(target_dir)) > 0:
        return False
    os.makedirs(target_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_dir)
        return True
    except Exception as e:
        print(f"  UNZIP FAIL: {e}")
        return None


def main():
    rows = parse_audit()
    print(f"Loaded {len(rows)} meetings from audit")

    for r in rows:
        meeting = r["meeting"]
        url = r["url"]
        ext = ".zip" if url.lower().endswith(".zip") else os.path.splitext(url)[1] or ".zip"
        local = os.path.join(DOWNLOADS, f"{meeting}{ext}")
        target = os.path.join(DATA_TABLES, str(meeting))

        downloaded = download(url, local)
        if downloaded is None:
            print(f"  M{meeting}: download failed")
            continue
        if downloaded:
            print(f"  M{meeting}: downloaded {os.path.getsize(local) // 1024} KB")
        else:
            print(f"  M{meeting}: cached")

        if ext == ".zip":
            extracted = unzip_to(local, target)
            if extracted:
                # Count files
                n = sum(1 for _, _, files in os.walk(target) for _ in files)
                print(f"    unzipped -> {target} ({n} files)")


if __name__ == "__main__":
    main()
