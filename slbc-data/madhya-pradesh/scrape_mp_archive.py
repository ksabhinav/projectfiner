#!/usr/bin/env python3
"""
MP SLBC archive scraper.

Source: https://www.slbcmadhyapradesh.in/slbc-meeting.aspx — index page
that lists 70+ SLBC meetings (130th, Dec 2007 → 197th, Mar 2026). Each
meeting row links to (a) agenda PDF, (b) data tables (XLSX from 2017+,
PDF before that), (c) minutes.

We follow each meeting link, find the data-table URL, download it, and
detect quarter from the URL naming convention
  Slbc-data-{mmm}{yy}-final-{YYYY-MM-DD}.xlsx
or extract from the meeting metadata.

Output: PDFs + XLSX files into slbc-data/madhya-pradesh/raw/
"""
import os, re, sys
from pathlib import Path
import urllib.request, urllib.parse, ssl
from html.parser import HTMLParser

SRC_DIR = Path(__file__).resolve().parent
RAW_DIR = SRC_DIR / 'raw'
RAW_DIR.mkdir(exist_ok=True)

INDEX_URL = 'https://www.slbcmadhyapradesh.in/slbc-meeting.aspx'
BASE = 'https://www.slbcmadhyapradesh.in/'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url, dest=None, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 FINER/1.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
        if dest:
            with open(dest, 'wb') as f:
                while True:
                    chunk = r.read(64*1024)
                    if not chunk: break
                    f.write(chunk)
            return os.path.getsize(dest)
        return r.read()

class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for k, v in attrs:
                if k == 'href' and v:
                    self.links.append(v)

def get_meeting_links():
    """Pull all meeting-detail page links from the archive index."""
    html = fetch(INDEX_URL).decode('utf-8', errors='replace')
    p = LinkExtractor(); p.feed(html)
    # Heuristic: meeting links look like meeting-detail.aspx?id=... or contain
    # "slbc-meeting" or PDF/XLSX direct links to MIS/upload_doc
    meeting_pages, direct_files = set(), set()
    for h in p.links:
        if not h: continue
        if 'meeting-detail' in h.lower() or '?meetingid' in h.lower():
            full = urllib.parse.urljoin(BASE, h)
            meeting_pages.add(full)
        elif h.lower().endswith(('.xlsx','.xls','.pdf')) and '/upload' in h.lower():
            full = urllib.parse.urljoin(BASE, h)
            direct_files.add(full)
    return sorted(meeting_pages), sorted(direct_files)

def main():
    print(f'Fetching index: {INDEX_URL}')
    meeting_pages, direct_files = get_meeting_links()
    print(f'  Meeting detail pages: {len(meeting_pages)}')
    print(f'  Direct file links: {len(direct_files)}')

    # Show sample of each
    print('\nSample meeting pages:')
    for u in meeting_pages[:5]: print(f'  {u}')
    print('\nSample direct files:')
    for u in direct_files[:10]: print(f'  {u}')

    # If we already have direct XLSX links from the index, just download them.
    # MP SLBC's index page typically lists every meeting's data file directly.
    target_files = [u for u in direct_files if u.lower().endswith('.xlsx')]
    print(f'\nXLSX targets to download: {len(target_files)}')
    if not target_files:
        # Some meetings might only have PDF data tables
        target_files = [u for u in direct_files if u.lower().endswith('.pdf') and 'data' in u.lower()]
        print(f'  No XLSX — falling back to PDF data tables: {len(target_files)}')

    downloaded = 0; skipped = 0
    for url in target_files:
        fname = url.split('/')[-1]
        dest = RAW_DIR / fname
        if dest.exists() and dest.stat().st_size > 1024:
            skipped += 1; continue
        try:
            sz = fetch(url, dest=dest, timeout=120)
            downloaded += 1
            print(f'  [{downloaded}] {fname} ({sz//1024} KB)')
        except Exception as e:
            print(f'  ! failed {fname}: {e}')

    print(f'\nDone. Downloaded {downloaded}, skipped {skipped} (cached). Files in {RAW_DIR}')

if __name__ == '__main__':
    main()
