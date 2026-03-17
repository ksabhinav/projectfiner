"""
RAG endpoint: BM25 search over SLBC NE meeting documents + Claude for answering.

POST /api/ask
Request:  { "question": "What KCC targets were set for Assam in 2024?" }
Response: { "answer": "...", "sources": [...] }
"""

import os
import re
import json
import math
from collections import Counter
from http.server import BaseHTTPRequestHandler

import anthropic

# ── Load index at cold start ──────────────────────────────────

INDEX_DIR = os.path.join(os.path.dirname(__file__), "index_data")

with open(os.path.join(INDEX_DIR, "chunks.json"), "r") as f:
    CHUNKS = json.load(f)

with open(os.path.join(INDEX_DIR, "bm25_params.json"), "r") as f:
    BM25 = json.load(f)


# ── BM25 Search ──────────────────────────────────────────────

def tokenize(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def bm25_search(query, top_k=8):
    query_tokens = tokenize(query)
    idf = BM25["idf"]
    doc_tfs = BM25["doc_tfs"]
    doc_lengths = BM25["doc_lengths"]
    avg_dl = BM25["avg_dl"]
    k1 = BM25["k1"]
    b = BM25["b"]
    n_docs = BM25["n_docs"]

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

        if score > 0:
            scores.append((i, score))

    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


# ── Claude Answering ─────────────────────────────────────────

SYSTEM_PROMPT = """You are a knowledgeable assistant for Project FINER, a financial inclusion research platform focused on India's North East region. You answer questions based on SLBC (State Level Bankers' Committee) meeting documents — both agenda booklets and minutes of meetings.

Guidelines:
- Answer based ONLY on the provided context. If the context doesn't contain enough information, say so clearly.
- Cite specific sources: mention the state, document type (booklet/minutes), and quarter when referencing information.
- Use precise numbers and data when available in the context.
- For financial figures, note they are typically in Rs. Lakhs (1 Lakh = Rs. 100,000).
- Keep answers concise but thorough. Use bullet points for multi-part answers.
- If the question is about a specific state, focus on that state's data.
- The NE states covered are: Assam, Meghalaya, Manipur, Mizoram, Nagaland, and Arunachal Pradesh."""


def ask_claude(question, context_chunks):
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

    # Build context from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        source = f"[{chunk['state']} | {chunk['type']} | {chunk['quarter']} | pages {chunk['page_start']}-{chunk['page_end']}]"
        context_parts.append(f"--- Source {i+1}: {source} ---\n{chunk['text']}")

    context = "\n\n".join(context_parts)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"""Based on the following excerpts from SLBC NE meeting documents, answer this question:

Question: {question}

Context:
{context}

Answer the question based on the context above. Cite the source documents when referencing specific information."""
            }
        ]
    )

    return message.content[0].text


# ── Handler ──────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON"})
            return

        question = data.get("question", "").strip()
        if not question:
            self._respond(400, {"error": "Missing 'question' field"})
            return

        if len(question) > 500:
            self._respond(400, {"error": "Question too long (max 500 chars)"})
            return

        # Optional state filter
        state_filter = data.get("state", "").strip() or None

        # BM25 search
        results = bm25_search(question, top_k=12)

        # Filter by state if requested
        context_chunks = []
        for idx, score in results:
            chunk = CHUNKS[idx]
            if state_filter and chunk["state"].lower() != state_filter.lower():
                continue
            context_chunks.append(chunk)
            if len(context_chunks) >= 6:
                break

        if not context_chunks:
            self._respond(200, {
                "answer": "I couldn't find any relevant information in the SLBC meeting documents for your question. Try rephrasing or broadening your query.",
                "sources": []
            })
            return

        # Ask Claude
        try:
            answer = ask_claude(question, context_chunks)
        except Exception as e:
            self._respond(500, {"error": f"Claude API error: {str(e)}"})
            return

        sources = [
            {
                "state": c["state"],
                "type": c["type"],
                "quarter": c["quarter"],
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "snippet": c["text"][:200].replace("\n", " "),
            }
            for c in context_chunks
        ]

        self._respond(200, {"answer": answer, "sources": sources})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
