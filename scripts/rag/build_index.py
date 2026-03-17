#!/usr/bin/env python3
"""
Build BM25 search index from extracted SLBC text files.

Input:  data/rag/text/{state}/{booklets|minutes}/*.txt
Output: data/rag/index/chunks.json (chunked text with metadata)
        data/rag/index/bm25_params.json (BM25 parameters: idf, avgdl, doc_count)

No API keys needed — pure local computation.
Uses BM25 (Okapi BM25) for retrieval, Claude for answering.
"""

import os
import re
import sys
import json
import math
from collections import Counter

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
TEXT_DIR = os.path.join(BASE_DIR, "data", "rag", "text")
INDEX_DIR = os.path.join(BASE_DIR, "data", "rag", "index")

CHUNK_TARGET_CHARS = 2000   # ~500 tokens
CHUNK_OVERLAP_CHARS = 200   # ~50 tokens overlap

# BM25 parameters
BM25_K1 = 1.5
BM25_B = 0.75


def tokenize(text):
    """Simple whitespace + punctuation tokenizer, lowercased."""
    return re.findall(r'[a-z0-9]+', text.lower())


def load_text_files():
    """Load all extracted text files with metadata."""
    documents = []

    for state in sorted(os.listdir(TEXT_DIR)):
        state_dir = os.path.join(TEXT_DIR, state)
        if not os.path.isdir(state_dir):
            continue

        for doc_type in ["booklets", "minutes", "tables"]:
            type_dir = os.path.join(state_dir, doc_type)
            if not os.path.isdir(type_dir):
                continue

            for fname in sorted(os.listdir(type_dir)):
                if not fname.endswith(".txt"):
                    continue

                fpath = os.path.join(type_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse metadata header
                meta = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].strip().split("\n"):
                            if ":" in line:
                                key, val = line.split(":", 1)
                                meta[key.strip()] = val.strip()
                        content = parts[2].strip()

                # Skip very short documents
                if len(content) < 100:
                    continue

                documents.append({
                    "state": meta.get("state", state),
                    "type": meta.get("type", doc_type.rstrip("s")),
                    "quarter": meta.get("quarter", "Unknown"),
                    "filename": meta.get("filename", fname),
                    "source_file": f"{state}/{doc_type}/{fname}",
                    "content": content,
                })

    return documents


def chunk_document(doc):
    """Split a document into overlapping chunks."""
    content = doc["content"]
    chunks = []

    # For table documents, use larger chunks to keep data together
    is_table = doc["type"] == "table"
    target = 8000 if is_table else CHUNK_TARGET_CHARS
    overlap = 400 if is_table else CHUNK_OVERLAP_CHARS

    # Split by page markers
    pages = re.split(r'\[Page \d+\]', content)
    pages = [p.strip() for p in pages if p.strip()]

    current_chunk = ""
    current_page_start = 1
    page_num = 0

    for page_text in pages:
        page_num += 1
        paragraphs = re.split(r'\n\n+', page_text)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > target and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "state": doc["state"],
                    "type": doc["type"],
                    "quarter": doc["quarter"],
                    "filename": doc["filename"],
                    "source_file": doc["source_file"],
                    "page_start": current_page_start,
                    "page_end": page_num,
                })

                # Keep overlap
                if len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:]
                current_page_start = page_num

            current_chunk += "\n\n" + para if current_chunk else para

    # Last chunk
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "state": doc["state"],
            "type": doc["type"],
            "quarter": doc["quarter"],
            "filename": doc["filename"],
            "source_file": doc["source_file"],
            "page_start": current_page_start,
            "page_end": page_num,
        })

    return chunks


def build_bm25_index(chunks):
    """Build BM25 index parameters from chunks."""
    # Tokenize all chunks
    doc_tokens = []
    doc_freqs = Counter()  # document frequency for each term

    for chunk in chunks:
        tokens = tokenize(chunk["text"])
        doc_tokens.append(tokens)
        # Count unique terms per document
        unique_terms = set(tokens)
        for term in unique_terms:
            doc_freqs[term] += 1

    n_docs = len(chunks)
    avg_dl = sum(len(t) for t in doc_tokens) / max(n_docs, 1)

    # Compute IDF for each term
    idf = {}
    for term, df in doc_freqs.items():
        idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

    # Store term frequencies per document
    doc_tfs = []
    for tokens in doc_tokens:
        tf = Counter(tokens)
        doc_tfs.append(dict(tf))

    return {
        "n_docs": n_docs,
        "avg_dl": avg_dl,
        "idf": idf,
        "doc_tfs": doc_tfs,
        "doc_lengths": [len(t) for t in doc_tokens],
        "k1": BM25_K1,
        "b": BM25_B,
    }


def bm25_search(query, bm25_params, top_k=10):
    """Search using BM25 scoring. Returns list of (chunk_idx, score)."""
    query_tokens = tokenize(query)
    idf = bm25_params["idf"]
    doc_tfs = bm25_params["doc_tfs"]
    doc_lengths = bm25_params["doc_lengths"]
    avg_dl = bm25_params["avg_dl"]
    k1 = bm25_params["k1"]
    b = bm25_params["b"]
    n_docs = bm25_params["n_docs"]

    scores = []
    for i in range(n_docs):
        score = 0.0
        dl = doc_lengths[i]
        tf_dict = doc_tfs[i]

        for token in query_tokens:
            if token not in idf:
                continue
            tf = tf_dict.get(token, 0)
            term_idf = idf[token]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avg_dl)
            score += term_idf * numerator / denominator

        scores.append((i, score))

    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


def main():
    print("Loading text files...")
    documents = load_text_files()
    print(f"  Loaded {len(documents)} documents")

    if not documents:
        print("No text files found. Run extract_text.py first.")
        sys.exit(1)

    # Chunk
    print("\nChunking documents...")
    all_chunks = []
    for doc in documents:
        doc_chunks = chunk_document(doc)
        all_chunks.extend(doc_chunks)

    # Add IDs
    for i, chunk in enumerate(all_chunks):
        chunk["id"] = i

    print(f"  Created {len(all_chunks)} chunks from {len(documents)} documents")

    chunk_lengths = [len(c["text"]) for c in all_chunks]
    print(f"  Avg chunk length: {sum(chunk_lengths) / len(chunk_lengths):.0f} chars")
    print(f"  Min: {min(chunk_lengths)}, Max: {max(chunk_lengths)}")

    # Per-state breakdown
    state_counts = {}
    for c in all_chunks:
        state_counts[c["state"]] = state_counts.get(c["state"], 0) + 1
    print(f"\n  Per-state chunks:")
    for state, count in sorted(state_counts.items()):
        print(f"    {state}: {count}")

    # Build BM25 index
    print("\nBuilding BM25 index...")
    bm25_params = build_bm25_index(all_chunks)
    print(f"  Vocabulary size: {len(bm25_params['idf'])}")
    print(f"  Avg document length: {bm25_params['avg_dl']:.0f} tokens")

    # Save chunks (text + metadata, no TF data)
    os.makedirs(INDEX_DIR, exist_ok=True)

    chunks_for_save = []
    for chunk in all_chunks:
        chunks_for_save.append({
            "id": chunk["id"],
            "text": chunk["text"],
            "state": chunk["state"],
            "type": chunk["type"],
            "quarter": chunk["quarter"],
            "filename": chunk["filename"],
            "source_file": chunk["source_file"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
        })

    chunks_path = os.path.join(INDEX_DIR, "chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks_for_save, f, ensure_ascii=False)
    chunks_size = os.path.getsize(chunks_path) / 1024 / 1024
    print(f"  Saved chunks: {chunks_path} ({chunks_size:.1f} MB)")

    # Save BM25 parameters (IDF + doc TFs + lengths)
    bm25_path = os.path.join(INDEX_DIR, "bm25_params.json")
    with open(bm25_path, "w", encoding="utf-8") as f:
        json.dump(bm25_params, f, ensure_ascii=False)
    bm25_size = os.path.getsize(bm25_path) / 1024 / 1024
    print(f"  Saved BM25 params: {bm25_path} ({bm25_size:.1f} MB)")

    # Test search
    print(f"\n{'='*60}")
    print("  TEST SEARCHES")
    print(f"{'='*60}")

    test_queries = [
        "KCC target Assam 2024",
        "CD ratio Meghalaya performance",
        "digital transactions financial inclusion",
        "PMJDY accounts Manipur",
        "branch network rural banking Nagaland",
    ]

    for query in test_queries:
        results = bm25_search(query, bm25_params, top_k=3)
        print(f"\n  Query: \"{query}\"")
        for idx, score in results:
            chunk = all_chunks[idx]
            snippet = chunk["text"][:120].replace("\n", " ")
            print(f"    [{score:.2f}] {chunk['state']} | {chunk['type']} | {chunk['quarter']} | p{chunk['page_start']}")
            print(f"           {snippet}...")

    print(f"\n{'='*60}")
    print(f"  INDEX BUILD COMPLETE")
    print(f"{'='*60}")
    print(f"  Documents: {len(documents)}")
    print(f"  Chunks: {len(all_chunks)}")
    print(f"  Vocabulary: {len(bm25_params['idf'])} terms")
    print(f"  Index files: {chunks_size + bm25_size:.1f} MB total")


if __name__ == "__main__":
    main()
