#!/usr/bin/env python3
"""
Extract plain text from downloaded SLBC NE PDFs.

Input:  data/rag/pdfs/{state}/{booklets|minutes}/*.pdf
Output: data/rag/text/{state}/{booklets|minutes}/*.txt

Each .txt file has a YAML-like metadata header followed by page-separated text.
Handles reversed text (common in Meghalaya/Assam landscape PDFs).
Flags PDFs with very little extracted text (likely scanned images).
"""

import os
import re
import sys

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber is required. Install with: pip3 install pdfplumber")
    sys.exit(1)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
PDF_DIR = os.path.join(BASE_DIR, "data", "rag", "pdfs")
TEXT_DIR = os.path.join(BASE_DIR, "data", "rag", "text")

# States and their display names
STATE_NAMES = {
    "assam": "Assam",
    "meghalaya": "Meghalaya",
    "manipur": "Manipur",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "arunachal-pradesh": "Arunachal Pradesh",
}

# Common English words for reversed-text detection
COMMON_WORDS = {"the", "and", "for", "that", "this", "with", "from", "district", "total",
                "bank", "branch", "credit", "loan", "amount", "quarter", "march", "june",
                "september", "december", "state", "rural", "urban", "number"}


def is_reversed_text(text):
    """Heuristic: check if text looks like it's character-reversed."""
    if not text or len(text) < 50:
        return False

    words = set(re.findall(r'[a-zA-Z]{3,}', text.lower()))
    reversed_words = set(w[::-1] for w in words)

    # Count how many words match common English when reversed
    forward_hits = len(words & COMMON_WORDS)
    reverse_hits = len(reversed_words & COMMON_WORDS)

    return reverse_hits > forward_hits and reverse_hits >= 3


def extract_page_text(page):
    """Extract text from a single pdfplumber page, handling reversed text."""
    text = page.extract_text() or ""

    # Check if text appears reversed (landscape-rotated pages)
    if is_reversed_text(text):
        # Reverse each line's characters
        lines = text.split("\n")
        text = "\n".join(line[::-1] for line in lines)

    return text


def clean_text(text):
    """Clean extracted text: normalize whitespace, remove artifacts."""
    # Collapse multiple blank lines to max 2
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    # Remove common PDF artifacts
    text = re.sub(r'(\x00|\x0c)', '', text)  # null bytes, form feeds
    # Normalize spaces (but keep newlines)
    text = re.sub(r'[^\S\n]+', ' ', text)
    # Strip trailing spaces on each line
    text = re.sub(r' +\n', '\n', text)
    return text.strip()


def guess_quarter(filename):
    """Try to extract quarter/period from the PDF filename."""
    fname = filename.lower()

    # Patterns like "Sept 2025", "June'24", "December 2023", "Mar'23"
    month_map = {
        'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
        'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
        'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December',
    }

    # Try "Month YYYY" or "Month'YY" patterns
    m = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*[\s\'_-]*(\d{2,4})', fname)
    if m:
        month_prefix = m.group(1)[:3]
        month = month_map.get(month_prefix, month_prefix.title())
        year = m.group(2)
        if len(year) == 2:
            year = "20" + year
        return f"{month} {year}"

    # Try YYYY-MM pattern
    m = re.search(r'(20\d{2})[-_](\d{2})', fname)
    if m:
        year = m.group(1)
        month_num = m.group(2)
        months = {'03': 'March', '06': 'June', '09': 'September', '12': 'December'}
        return f"{months.get(month_num, month_num)} {year}"

    return "Unknown"


def extract_pdf(pdf_path, state, doc_type):
    """Extract text from a single PDF and save as .txt file."""
    filename = os.path.basename(pdf_path)
    txt_name = os.path.splitext(filename)[0] + ".txt"

    out_dir = os.path.join(TEXT_DIR, state, doc_type)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, txt_name)

    # Skip if already extracted
    if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
        return "skipped", 0

    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        return f"error: {e}", 0

    pages_text = []
    total_chars = 0

    for i, page in enumerate(pdf.pages):
        try:
            text = extract_page_text(page)
            text = clean_text(text)
            total_chars += len(text)
            pages_text.append(f"[Page {i + 1}]\n{text}")
        except Exception as e:
            pages_text.append(f"[Page {i + 1}]\n[ERROR extracting page: {e}]")

    pdf.close()

    num_pages = len(pages_text)
    quarter = guess_quarter(filename)
    state_display = STATE_NAMES.get(state, state.title())

    # Build output with metadata header
    header = f"""---
state: {state_display}
type: {doc_type.rstrip('s')}
quarter: {quarter}
filename: {filename}
pages: {num_pages}
chars: {total_chars}
---"""

    full_text = header + "\n\n" + "\n\n".join(pages_text)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    # Flag low-text PDFs (likely scanned)
    avg_chars_per_page = total_chars / max(num_pages, 1)
    if avg_chars_per_page < 100 and num_pages > 2:
        return "low-text", num_pages
    return "ok", num_pages


def main():
    total_ok = 0
    total_low = 0
    total_error = 0
    total_skipped = 0
    total_pages = 0
    low_text_files = []

    for state in sorted(STATE_NAMES.keys()):
        for doc_type in ["booklets", "minutes"]:
            pdf_dir = os.path.join(PDF_DIR, state, doc_type)
            if not os.path.isdir(pdf_dir):
                continue

            pdfs = sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf"))
            if not pdfs:
                continue

            print(f"\n  {state}/{doc_type}: {len(pdfs)} PDFs")

            for pdf_name in pdfs:
                pdf_path = os.path.join(pdf_dir, pdf_name)
                status, pages = extract_pdf(pdf_path, state, doc_type)

                if status == "skipped":
                    total_skipped += 1
                elif status == "ok":
                    total_ok += 1
                    total_pages += pages
                    print(f"    OK: {pdf_name} ({pages} pages)")
                elif status == "low-text":
                    total_low += 1
                    total_pages += pages
                    low_text_files.append(f"{state}/{doc_type}/{pdf_name}")
                    print(f"    LOW-TEXT: {pdf_name} ({pages} pages) — possibly scanned")
                else:
                    total_error += 1
                    print(f"    ERROR: {pdf_name} — {status}")

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Extracted: {total_ok}")
    print(f"  Low-text (possibly scanned): {total_low}")
    print(f"  Errors: {total_error}")
    print(f"  Skipped (already done): {total_skipped}")
    print(f"  Total pages processed: {total_pages}")

    if low_text_files:
        print(f"\n  Low-text files (may need OCR):")
        for f in low_text_files:
            print(f"    - {f}")


if __name__ == "__main__":
    main()
