#!/usr/bin/env python3
"""
Generate concise summaries of SLBC NE meeting minutes using Claude API.

Input:  data/rag/text/{state}/minutes/*.txt
Output: public/slbc-data/ne-meeting-summaries.json

Uses the Anthropic Messages API directly (no SDK dependency).
Requires ANTHROPIC_API_KEY environment variable.
"""

import os
import re
import ssl
import sys
import json
import time
import urllib.request

# macOS Python often lacks default SSL certs
SSL_CTX = ssl.create_default_context()
try:
    import certifi
    SSL_CTX.load_verify_locations(certifi.where())
except ImportError:
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
TEXT_DIR = os.path.join(BASE_DIR, "data", "rag", "text")
OUTPUT_PATH = os.path.join(BASE_DIR, "public", "slbc-data", "ne-meeting-summaries.json")

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: Set ANTHROPIC_API_KEY environment variable")
    sys.exit(1)

STATES = ["assam", "meghalaya", "manipur", "mizoram", "nagaland", "arunachal-pradesh"]

STATE_DISPLAY = {
    "assam": "Assam",
    "meghalaya": "Meghalaya",
    "manipur": "Manipur",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "arunachal-pradesh": "Arunachal Pradesh",
}

SYSTEM_PROMPT = """You are summarizing SLBC (State Level Bankers' Committee) meeting minutes from India's North East region. Create a concise summary with these sections:

1. **Key Decisions** (2-4 bullet points): Major policy decisions, targets set, directives issued
2. **Performance Highlights** (2-3 bullet points): Notable achievements, improvements, or shortfalls discussed
3. **Action Items** (2-3 bullet points): Follow-up actions assigned to banks or government departments

Rules:
- Keep the entire summary under 200 words
- Use specific numbers/percentages when available
- Mention specific banks or districts only when they're central to the point
- If the text is mostly tabular data with little narrative, summarize what the tables show
- Output plain text with markdown bold (**) for section headers only"""


def summarize_text(text, state, quarter):
    """Send text to Claude for summarization."""
    # Truncate to ~8000 chars to stay within token limits and keep costs down
    if len(text) > 8000:
        text = text[:8000] + "\n\n[... truncated for summarization ...]"

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 400,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Summarize these SLBC meeting minutes from {STATE_DISPLAY.get(state, state)}, {quarter}:\n\n{text}"
            }
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return result["content"][0]["text"]


def parse_metadata(content):
    """Extract metadata header from text file."""
    meta = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            content = parts[2].strip()
    return meta, content


def main():
    # Load existing summaries to allow resume
    existing = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r") as f:
            data = json.load(f)
            for s in data.get("summaries", []):
                existing[s["source_file"]] = s

    summaries = list(existing.values())
    new_count = 0
    error_count = 0

    for state in STATES:
        minutes_dir = os.path.join(TEXT_DIR, state, "minutes")
        if not os.path.isdir(minutes_dir):
            continue

        files = sorted(f for f in os.listdir(minutes_dir) if f.endswith(".txt"))
        print(f"\n  {STATE_DISPLAY.get(state, state)}: {len(files)} minutes files")

        for fname in files:
            source_file = f"{state}/minutes/{fname}"

            # Skip if already summarized
            if source_file in existing:
                continue

            fpath = os.path.join(minutes_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            meta, text = parse_metadata(content)
            quarter = meta.get("quarter", "Unknown")

            # Skip very short files
            if len(text) < 200:
                print(f"    SKIP (too short): {fname}")
                continue

            print(f"    Summarizing: {fname} ({quarter})...", end=" ", flush=True)

            try:
                summary = summarize_text(text, state, quarter)
                summaries.append({
                    "state": STATE_DISPLAY.get(state, state),
                    "state_slug": state,
                    "quarter": quarter,
                    "filename": meta.get("filename", fname),
                    "source_file": source_file,
                    "pages": int(meta.get("pages", 0)),
                    "summary": summary,
                })
                new_count += 1
                print("OK")

                # Rate limiting — be polite
                time.sleep(1)

                # Save incrementally every 5 summaries
                if new_count % 5 == 0:
                    _save(summaries)

            except Exception as e:
                error_count += 1
                print(f"ERROR: {e}")

    _save(summaries)

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  New summaries: {new_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {len(summaries)}")
    print(f"  Saved to: {OUTPUT_PATH}")


def _save(summaries):
    """Save summaries sorted by state then quarter."""
    # Sort: by state, then try to sort by quarter date
    def sort_key(s):
        q = s.get("quarter", "Unknown")
        # Try to parse "Month YYYY" into sortable format
        month_map = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12',
        }
        parts = q.lower().split()
        if len(parts) == 2 and parts[0] in month_map:
            return (s["state"], f"{parts[1]}-{month_map[parts[0]]}")
        return (s["state"], q)

    summaries.sort(key=sort_key)

    output = {
        "generated": time.strftime("%Y-%m-%d"),
        "count": len(summaries),
        "summaries": summaries,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
