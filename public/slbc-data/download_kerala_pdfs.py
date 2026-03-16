#!/usr/bin/env python3
"""Download Kerala SLBC annexure PDFs (2020-2025)."""
import os, time, requests, warnings
warnings.filterwarnings('ignore')

BASE = "https://slbckerala.com/images/Meetings"
OUT = os.path.join(os.path.dirname(__file__), "kerala/pdfs")
os.makedirs(OUT, exist_ok=True)

# Meeting → (quarter_key, annexure_path)
MEETINGS = {
    "SLBC148_Dec2025": ("2025-12", "086e2978-9b8c-4a01-b395-67f54232fbbb-annexures (1).pdf"),
    "SLBC147_Sep2025": ("2025-09", "5fcc091f-8f6a-4c27-bdcc-6cb0bfe1fe0c-ANNEXURES SEP25.pdf"),
    "SLBC146_Jun2025": ("2025-06", "cf549c2c-9268-4126-a5f9-84b0bf8faa0c-ANNEXURES (2).pdf"),
    "SLRM2025_Mar2025": ("2025-03", "d0cbfa7b-c1b5-4708-9325-c5e38f34aea5-ANNEXURE.pdf"),
    "SLBC145_Dec2024": ("2024-12", "93857ece-4ac8-4b75-86ec-5401c0b32767-Annexures SLBC145.pdf"),
    "SLBC144_Sep2024": ("2024-09", "f5265ce4-c157-4d57-b431-b2701d2f31fc-Annexures SLBC 144.pdf"),
    "SLBC143_Jun2024": ("2024-06", "ae9338eb-22bc-415d-9d46-8a41822e6fa3-SLBC143Annexures_up.pdf"),
    "SLRM2024_Mar2024": ("2024-03", "54245e0d-fae8-4c1b-b17d-a95cad7d8836-Annexures with Vitals.pdf"),
    "SLBC142_Dec2023": ("2023-12", "e5563145-1435-4487-a39f-dd06c7f4aa63-Annexures Merged with vitals up.pdf"),
    "SLBC141_Sep2023": ("2023-09", "c29a5ad0-2d99-41c4-8eef-bff58e0bae32-Annexures SLBC 141.pdf"),
    "SLBC140_Jun2023": ("2023-06", "945dc26f-b1e9-40a1-8296-f0c66fd36525-Annexures SLBC 140 June 2023.pdf"),
    "SLRM2023_Mar2023": ("2023-03", "2644aaaf-4bfc-47a8-bf29-895913071247-annexures.pdf"),
    "SLBC139_Dec2022": ("2022-12", "15e1f728-4f98-459e-b4fe-ab420ee8fddb-139 SLBC Book_Final.pdf"),
    "SLBC138_Sep2022": ("2022-09", "4323400a-8915-4c29-a1ce-ef3733a956b0-Annexure_Sep_2022.pdf"),
    "SLBC137_Jun2022": ("2022-06", "9f0c0faa-82f4-4116-a753-b38cf6627560-Book_Final.pdf"),
    "SLRM2022_Mar2022": ("2022-03", "5dd6e068-0f92-4170-a478-65dcc8a87b53-Annexures_SLRM2022.pdf"),
    "SLBC136_Dec2021": ("2021-12", "5ba9eb15-fc9a-4f24-96b3-30a2ec42592e-Annexures_136SLBC_December 2021.pdf"),
    "SLBC135_Sep2021": ("2021-09", "60beb806-335c-4d45-9533-eae4c0c4f9c0-135_SLBC_Annexures.pdf"),
    "SLBC134_Jun2021": ("2021-06", "776d1960-2ad6-4f02-a2f8-529eaefcb540-134th SLBC Booklet.pdf"),
    "SLRM2021_Mar2021": ("2021-03", "1129927e-e95a-4442-af50-6bcb7f7bd771-Annexures_March 2021.pdf"),
    "SLBC133_Dec2020": ("2020-12", "fc6c2b41-af8c-4c4f-a024-5cbde69de1c4-Final_Book.pdf"),
    "SLBC131_Jun2020": ("2020-06", "508cd764-9c42-430a-97d9-fe543fcb0f18-131 SLBC Annexures.pdf"),
    "SLRM2020_Mar2020": ("2020-03", "df87b159-badf-48ee-9ccc-d5bd8690382a-SLRM 2020 Annexures.pdf"),
}

sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0"})
sess.verify = False

for name, (qkey, path) in MEETINGS.items():
    out_path = os.path.join(OUT, f"{qkey}_{name}.pdf")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
        print(f"  [skip] {name} already downloaded")
        continue
    url = f"{BASE}/{path}"
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
