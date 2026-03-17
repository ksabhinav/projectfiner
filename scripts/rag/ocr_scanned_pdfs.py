#!/usr/bin/env python3
"""
OCR scanned PDFs that pdfplumber couldn't extract text from.
Overwrites the .txt files with OCR-extracted text.
"""

import os
import sys
import glob
from pdf2image import convert_from_path
import pytesseract

TEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "rag", "text")
PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "rag", "pdfs")

def get_content_chars(txt_path):
    """Count non-metadata content chars in a text file."""
    skip_prefixes = ("---", "state:", "type:", "quarter:", "filename:", "pages:", "chars:", "[Page")
    total = 0
    with open(txt_path) as f:
        for line in f:
            stripped = line.strip()
            if stripped and not any(stripped.startswith(p) for p in skip_prefixes):
                total += len(stripped)
    return total

def ocr_pdf(pdf_path):
    """Convert PDF to images and OCR each page."""
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        print(f"    ERROR converting to images: {e}")
        return None

    pages_text = []
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang='eng')
        pages_text.append(text.strip())
        print(f"    Page {i+1}/{len(images)}: {len(text)} chars")

    return pages_text

def main():
    # Find all text files with 0 or near-0 content
    states = ["meghalaya", "assam", "manipur", "mizoram", "nagaland", "arunachal-pradesh"]

    # Allow filtering to specific state
    if len(sys.argv) > 1:
        states = [sys.argv[1]]

    total_ocrd = 0
    for state in states:
        txt_dir = os.path.join(TEXT_DIR, state, "minutes")
        pdf_dir = os.path.join(PDF_DIR, state, "minutes")

        if not os.path.isdir(txt_dir):
            continue

        txt_files = sorted(glob.glob(os.path.join(txt_dir, "*.txt")))
        empty_files = []

        for txt_path in txt_files:
            chars = get_content_chars(txt_path)
            if chars < 200:  # Less than 200 content chars = needs OCR
                empty_files.append(txt_path)

        if not empty_files:
            print(f"{state}: all files have content, skipping")
            continue

        print(f"\n{state}: {len(empty_files)} files need OCR")

        for txt_path in empty_files:
            fname = os.path.basename(txt_path).replace(".txt", ".pdf")
            pdf_path = os.path.join(pdf_dir, fname)

            if not os.path.exists(pdf_path):
                print(f"  SKIP {fname}: PDF not found")
                continue

            print(f"  OCR: {fname}")
            pages_text = ocr_pdf(pdf_path)

            if pages_text is None:
                continue

            total_chars = sum(len(p) for p in pages_text)
            if total_chars < 50:
                print(f"    SKIP: OCR produced only {total_chars} chars")
                continue

            # Read existing metadata from txt file
            metadata_lines = []
            with open(txt_path) as f:
                in_meta = False
                for line in f:
                    if line.strip() == "---":
                        metadata_lines.append(line)
                        if in_meta:
                            break
                        in_meta = True
                    elif in_meta:
                        metadata_lines.append(line)

            # Update chars in metadata
            new_meta = []
            for line in metadata_lines:
                if line.startswith("chars:"):
                    new_meta.append(f"chars: {total_chars}\n")
                else:
                    new_meta.append(line)

            # Write updated file
            with open(txt_path, "w") as f:
                for line in new_meta:
                    f.write(line)
                f.write("\n")
                for i, page_text in enumerate(pages_text):
                    f.write(f"[Page {i+1}]\n")
                    f.write(page_text)
                    f.write("\n\n")

            print(f"    OK: {total_chars} chars from {len(pages_text)} pages")
            total_ocrd += 1

    print(f"\nDone! OCR'd {total_ocrd} files")

if __name__ == "__main__":
    main()
