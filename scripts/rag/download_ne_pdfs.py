#!/usr/bin/env python3
"""
Download SLBC NE meeting PDFs (booklets + minutes) for all available states.

Source: https://slbcne.nic.in/{state}/{booklet|minutes}.php

Downloads to: data/rag/pdfs/{state}/{booklets|minutes}/*.pdf
Also handles .zip files by extracting PDFs from them.
Resume-friendly: skips already-downloaded files.
"""

import os
import re
import ssl
import sys
import time
import zipfile
import tempfile
import urllib.request
import urllib.parse
from html.parser import HTMLParser

# ── Configuration ──────────────────────────────────────────────

BASE_URL = "https://slbcne.nic.in"

STATES = {
    "assam": "assam",
    "meghalaya": "meghalaya",
    "manipur": "manipur",
    "mizoram": "mizoram",
    "nagaland": "nagaland",
    "arunachal-pradesh": "ap",
}

PAGE_TYPES = ["booklet", "minutes"]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "rag", "pdfs")

# Skip these formats (too few to bother with, need special handling)
SKIP_EXTENSIONS = {".doc", ".docx", ".rar", ".xls", ".xlsx"}

# SSL context that doesn't verify (govt sites often have cert issues)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ── HTML Link Extractor ───────────────────────────────────────

class LinkExtractor(HTMLParser):
    """Extract all <a href="..."> links from HTML."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def fetch_page(url):
    """Fetch a URL and return its HTML content."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ProjectFINER)"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def download_file(url, dest_path):
    """Download a file to dest_path. Returns True on success."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ProjectFINER)"})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=120) as resp:
            data = resp.read()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  ERROR downloading {url}: {e}")
        return False


def extract_pdfs_from_zip(zip_path, dest_dir):
    """Extract any .pdf files from a zip archive into dest_dir. Returns list of extracted paths."""
    extracted = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.lower().endswith(".pdf") and not name.startswith("__MACOSX"):
                    # Flatten: use just the filename, not nested dirs
                    fname = os.path.basename(name)
                    if not fname:
                        continue
                    dest = os.path.join(dest_dir, fname)
                    if not os.path.exists(dest):
                        with zf.open(name) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                    extracted.append(dest)
    except zipfile.BadZipFile:
        print(f"  WARNING: Bad zip file: {zip_path}")
    return extracted


def sanitize_filename(name):
    """Make a filename safe for the filesystem."""
    # Decode URL encoding
    name = urllib.parse.unquote(name)
    # Replace problematic chars
    name = re.sub(r'[<>:"|?*]', '_', name)
    # Collapse multiple spaces/underscores
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def scrape_and_download(state_name, state_path, page_type):
    """Scrape a booklet/minutes page and download all PDFs."""
    url = f"{BASE_URL}/{state_path}/{page_type}.php"
    print(f"\n{'='*60}")
    print(f"  {state_name} — {page_type}")
    print(f"  {url}")
    print(f"{'='*60}")

    html = fetch_page(url)
    if not html:
        return 0, 0, 0

    # Parse links
    parser = LinkExtractor()
    parser.feed(html)

    # Filter to downloadable files
    pdf_links = []
    zip_links = []
    skipped = []

    for link in parser.links:
        # Skip external links, anchors, php pages
        if link.startswith("http") and BASE_URL not in link:
            continue
        if link.startswith("#") or link.endswith(".php"):
            continue

        ext = os.path.splitext(link.lower())[1]
        if ext == ".pdf":
            pdf_links.append(link)
        elif ext == ".zip":
            zip_links.append(link)
        elif ext in SKIP_EXTENSIONS:
            skipped.append(link)

    if skipped:
        print(f"  Skipping {len(skipped)} non-PDF files: {[os.path.basename(s) for s in skipped]}")

    folder_name = page_type if page_type.endswith("s") else f"{page_type}s"
    dest_dir = os.path.join(OUTPUT_DIR, state_name, folder_name)
    os.makedirs(dest_dir, exist_ok=True)

    downloaded = 0
    already_exists = 0

    # Download PDFs
    for link in pdf_links:
        # Build full URL
        if link.startswith("http"):
            full_url = link
        else:
            # Relative URL — resolve against the page's directory
            full_url = f"{BASE_URL}/{state_path}/{urllib.parse.quote(link, safe='/:@!$&\'()*+,;=-._~')}"

        fname = sanitize_filename(os.path.basename(link))
        dest_path = os.path.join(dest_dir, fname)

        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            already_exists += 1
            continue

        print(f"  Downloading: {fname}")
        if download_file(full_url, dest_path):
            downloaded += 1
            time.sleep(0.5)  # Be polite
        else:
            # Try without URL encoding (some filenames have spaces in the URL)
            alt_url = f"{BASE_URL}/{state_path}/{link}"
            if download_file(alt_url, dest_path):
                downloaded += 1
                time.sleep(0.5)

    # Download and extract ZIPs
    for link in zip_links:
        if link.startswith("http"):
            full_url = link
        else:
            full_url = f"{BASE_URL}/{state_path}/{urllib.parse.quote(link, safe='/:@!$&\'()*+,;=-._~')}"

        fname = sanitize_filename(os.path.basename(link))
        print(f"  Downloading ZIP: {fname}")

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name

        if download_file(full_url, tmp_path):
            extracted = extract_pdfs_from_zip(tmp_path, dest_dir)
            downloaded += len(extracted)
            if extracted:
                print(f"    Extracted {len(extracted)} PDFs from ZIP")
            else:
                print(f"    WARNING: No PDFs found in ZIP")
            time.sleep(0.5)

        # Clean up temp zip
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    total = downloaded + already_exists
    print(f"  Result: {downloaded} new, {already_exists} already existed, {total} total PDFs")
    return downloaded, already_exists, total


def main():
    total_new = 0
    total_existing = 0
    total_all = 0

    for state_name, state_path in STATES.items():
        for page_type in PAGE_TYPES:
            new, existing, total = scrape_and_download(state_name, state_path, page_type)
            total_new += new
            total_existing += existing
            total_all += total

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  New downloads: {total_new}")
    print(f"  Already existed: {total_existing}")
    print(f"  Total PDFs: {total_all}")

    # Print per-state counts
    print(f"\n  Per-state breakdown:")
    for state_name in STATES:
        for ptype in PAGE_TYPES:
            d = os.path.join(OUTPUT_DIR, state_name, f"{ptype}s")
            if os.path.isdir(d):
                count = len([f for f in os.listdir(d) if f.lower().endswith(".pdf")])
                print(f"    {state_name}/{ptype}s: {count} PDFs")


if __name__ == "__main__":
    main()
