#!/usr/bin/env python3
"""Download Karnataka SLBC annexure PDFs and Excel files (2020-2025)."""
import os, time, requests, warnings
warnings.filterwarnings('ignore')

BASE = "https://slbckarnataka.com/userfiles/slbc"
OUT = os.path.join(os.path.dirname(__file__), "karnataka/pdfs")
os.makedirs(OUT, exist_ok=True)

# Meeting → (quarter_key, filename(s))
MEETINGS = {
    "171_Jun2025": ("2025-06", ["ANNEX_171_300625_SLBC_MEETING_DT_01092025.pdf"]),
    "169_Mar2025": ("2025-03", ["ANNEX_169_310325_SLBC_MEETING_14052025.pdf"]),
    "168": ("2024-12", ["168th_SLBC_ ANNEXURES.pdf"]),
    "167_Sep2024": ("2024-09", ["ANNEX_167_300924_SLBC_MEETING FINAL.pdf"]),
    "166_Aug2024": ("2024-06", ["ANNEX_166_SLBC_MEETING_13082024 FINAL.pdf"]),
    "165": ("2024-03", ["ANNEXURES_165th_SLBC_Meeting.pdf"]),
    "164": ("2023-12", ["164_SLBC_Annexures.pdf"]),
    "163_Dec2018": ("2023-09", ["163 Annexures 1.pdf"]),
    # Older meetings with Excel
    "155": ("2022-03", ["All Annexures_155th SLBC.xlsx"]),
    "153": ("2021-09", ["153_All_Annexures.xlsx"]),
    "152": ("2021-06", ["All%20Annexures.xlsx"]),
    "151_Jun2020": ("2020-06", ["All Annexures_June 2020.xlsx"]),
    "150_Jun2020": ("2020-03", ["Annexures - 150 SLBC Meeting.xlsx"]),
}

sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0"})
sess.verify = False

for name, (qkey, files) in MEETINGS.items():
    for fname in files:
        ext = fname.split('.')[-1]
        out_path = os.path.join(OUT, f"{qkey}_{name}.{ext}")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"  [skip] {name}/{fname} already downloaded")
            continue
        url = f"{BASE}/{fname}"
        print(f"  Downloading {name} ({qkey})...", end=" ", flush=True)
        try:
            r = sess.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(out_path, 'wb') as f:
                    f.write(r.content)
                print(f"{len(r.content)/1024/1024:.1f}MB")
            else:
                print(f"FAILED (status={r.status_code}, size={len(r.content)})")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(1)

print("\nDone!")
