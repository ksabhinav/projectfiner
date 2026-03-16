#!/usr/bin/env python3
"""Download Tamil Nadu SLBC agenda PDFs."""
import os, time, re, requests, warnings
from bs4 import BeautifulSoup
warnings.filterwarnings('ignore')

BASE = "https://www.slbctn.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tamil-nadu/pdfs")
os.makedirs(OUT, exist_ok=True)

sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
sess.verify = False

# Fetch page and extract all onclick URLs
r = sess.get(f"{BASE}/SLBC_Meeting_Held.aspx", timeout=30)
soup = BeautifulSoup(r.content, 'lxml')

# Extract agenda PDFs from onclick handlers
# The onclick handlers are in table rows: index, agenda, table_agenda, minutes
# We want the "Main Agenda" PDFs which contain annexures with data

agenda_pdfs = []
for elem in soup.find_all(attrs={"onclick": True}):
    onclick = elem.get("onclick", "")
    match = re.search(r"openLink\('([^']+)'\)", onclick)
    if match:
        path = match.group(1).strip()
        if path and path.startswith('uploads/') and path.endswith('.pdf'):
            # Get agenda PDFs (contain "Agenda" in filename)
            if 'agenda' in path.lower() or 'SLBC' in path:
                agenda_pdfs.append(path)

# Also get from the raw HTML for meeting correlation
# Parse table rows to correlate meeting numbers with dates and URLs
table_rows = soup.find_all('tr')
meetings = []
for row in table_rows:
    cells = row.find_all('td')
    if len(cells) >= 4:
        # Try to find meeting number and date
        texts = [c.get_text(strip=True) for c in cells[:3]]
        # Find all onclick URLs in this row
        row_urls = []
        for link in row.find_all(attrs={"onclick": True}):
            m = re.search(r"openLink\('([^']+)'\)", link.get("onclick", ""))
            if m and m.group(1).strip().endswith('.pdf'):
                row_urls.append(m.group(1).strip())

        if row_urls and any(t for t in texts):
            meetings.append((texts, row_urls))

print(f"Found {len(meetings)} meeting rows")

# Map meeting numbers to quarters (TN has quarterly meetings)
# Meeting dates from the page: 185th=06.02.2026, 184th=19.11.2025, 183rd=06.08.2025, etc.
MEETING_QUARTERS = {
    "185": "2025-12",  # Feb 2026 meeting = Dec 2025 data
    "184": "2025-09",  # Nov 2025 meeting = Sep 2025 data
    "183": "2025-06",  # Aug 2025 meeting = Jun 2025 data
    "182": "2025-03",  # May 2025 meeting = Mar 2025 data
    "181": "2024-12",  # Feb 2025 meeting = Dec 2024 data
    "180": "2024-09",  # Nov 2024 meeting = Sep 2024 data
    "179": "2024-06",  # Aug 2024 meeting = Jun 2024 data
    "178": "2024-03",  # May 2024 meeting = Mar 2024 data
    "177": "2023-12",  # Feb 2024 meeting = Dec 2023 data
    "176": "2023-09",  # Nov 2023 meeting = Sep 2023 data
    "175": "2023-06",  # Aug 2023 meeting = Jun 2023 data
    "174": "2023-03",  # May 2023 meeting = Mar 2023 data
    "173": "2022-12",  # Feb 2023 meeting = Dec 2022 data
    "172": "2022-09",  # Nov 2022 meeting = Sep 2022 data
    "171": "2022-06",  # Aug 2022 meeting = Jun 2022 data
    "170": "2022-03",  # May 2022 meeting = Mar 2022 data
    "169": "2021-12",  # Feb 2022 meeting = Dec 2021 data
    "168": "2021-09",  # Nov 2021 meeting = Sep 2021 data
    "167": "2021-06",  # Aug 2021 meeting = Jun 2021 data
    "166": "2021-03",  # May 2021 meeting = Mar 2021 data
    "165": "2020-12",  # Feb 2021 meeting = Dec 2020 data
    "164": "2020-09",  # Nov 2020 meeting = Sep 2020 data
    "163": "2020-06",  # Aug 2020 meeting = Jun 2020 data
    "162": "2020-03",  # May 2020 meeting = Mar 2020 data
    "161": "2019-12",
    "160": "2019-09",
    "159": "2019-06",
    "158": "2019-03",
}

# Download agenda PDFs for recent meetings
AGENDA_URLS = {
    "185": "uploads/185th  - Main Agenda Final.pdf",
    "184": "uploads/184th  - Main Agenda Final.pdf",
    "183": "uploads/CEDocuments/183rd  - Main Agenda V6.pdf",
    "182": "uploads/CEDocuments/182nd - Main Agenda-V8.pdf",
    "181": "uploads/CEDocuments/181th - Main Agenda-Final.pdf",
    "180": "uploads/CEDocuments/180th - Main Agenda- Final.pdf",
    "179": "uploads/CEDocuments/179th - Main Agenda.pdf",
    "178": "uploads/CEDocuments/178th Agenda PDF.pdf",
    "177": "uploads/CEDocuments/177th SLBC Agenda-Final.pdf",
    "176": "uploads/CEDocuments/176 Agenda Final Approved.pdf",
    "174": "uploads/CEDocuments/174 SLBC_Agenda Matters.pdf",
    "173": "uploads/CEDocuments/173rd Agenda.pdf",
    "172": "uploads/CEDocuments/172nd Agenda.pdf",
    "171": "uploads/CEDocuments/171st SLBC Agenda papers.pdf",
    "170": "uploads/CEDocuments/AGENDA 170 SLBC-F.pdf",
    "169": "uploads/CEDocuments/169 slbc - uploaded data - slbc site.pdf",
    "168": "uploads/CEDocuments/slbc.pdf",
    "167": "uploads/CEDocuments/167 SLBC MAIN MEETING.pdf",
    "166": "uploads/CEDocuments/166-SLBC-AGENDA-MATERIAL.pdf",
    "165": "uploads/CEDocuments/slbc Agenda.pdf",
    "163": "uploads/CEDocuments/163rd slbc Agenda.pdf",
    "162": "uploads/CEDocuments/162 SLBC.pdf",
    "160": "uploads/CEDocuments/160th Slbc Agenda Book.pdf",
    "159": "uploads/CEDocuments/159TH SLBC - Agenda Book.pdf",
    "158": "uploads/CEDocuments/Agenda 158th SLBC.pdf",
    "156": "uploads/CEDocuments/slbc156 agenda book.pdf",
    "155": "uploads/CEDocuments/155th SLBC Agenda.pdf",
    "154": "uploads/CEDocuments/154th SLBC Agenda.pdf",
    "153": "uploads/CEDocuments/153rd SLBC Agenda.pdf",
    "152": "uploads/CEDocuments/152nd SLBC  Agenda.pdf",
    "151": "uploads/CEDocuments/151st SLBC Agenda.pdf",
    "150": "uploads/CEDocuments/150th SLBC Agenda.pdf",
}

for meeting_num, path in sorted(AGENDA_URLS.items(), key=lambda x: int(x[0]), reverse=True):
    qkey = MEETING_QUARTERS.get(meeting_num, f"meeting_{meeting_num}")
    out_path = os.path.join(OUT, f"{qkey}_{meeting_num}th_Agenda.pdf")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
        print(f"  [skip] {meeting_num}th already downloaded")
        continue

    url = f"{BASE}/{path}"
    print(f"  Downloading {meeting_num}th ({qkey})...", end=" ", flush=True)
    try:
        r = sess.get(url, timeout=60)
        if r.status_code == 200 and len(r.content) > 1000:
            # Check if it's actually a PDF
            if r.content[:4] == b'%PDF':
                with open(out_path, 'wb') as f:
                    f.write(r.content)
                print(f"{len(r.content)/1024/1024:.1f}MB")
            else:
                print(f"NOT A PDF (got HTML/other)")
        else:
            print(f"FAILED (status={r.status_code})")
    except Exception as e:
        print(f"ERROR: {e}")
    time.sleep(1)

print("\nDone!")
