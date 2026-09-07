"""
RAG endpoint: BM25 search over SLBC meeting documents + Llama via Groq.

POST /api/ask
Request:  { "question": "What KCC targets were set for Assam in 2024?" }
Response: { "answer": "...", "sources": [...] }
"""

import os
import re
import json
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler
from threading import Lock
from time import monotonic

MAX_BODY_BYTES = 4096
DEFAULT_ALLOWED_ORIGINS = {
    "https://projectfiner.com",
    "https://www.projectfiner.com",
}


# These limits are deliberately conservative defaults. They are process-local
# defense-in-depth for the separately deployed serverless API; the deployment
# should also apply provider/edge quotas for a shared global budget.
MAX_RATE_BUCKETS = 10000
_CLIENT_REQUESTS = defaultdict(deque)
_TOTAL_REQUESTS = deque()
_RATE_LOCK = Lock()


def _env_int(name, default, minimum=1, maximum=86400):
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _rate_limit_config():
    return {
        "client_limit": _env_int("ASK_MAX_REQUESTS_PER_CLIENT", 10, 1, 1000),
        "client_window": _env_int("ASK_CLIENT_WINDOW_SECONDS", 60, 1, 86400),
        "total_limit": _env_int("ASK_MAX_REQUESTS_PER_WINDOW", 500, 1, 10000),
        "total_window": _env_int("ASK_TOTAL_WINDOW_SECONDS", 86400, 60, 604800),
    }


def _request_client_key(request):
    headers = getattr(request, "headers", {})
    forwarded = headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:128] or "unknown"

    address = getattr(request, "client_address", None)
    if address:
        return str(address[0])[:128]
    return "unknown"


def _seconds_until(timestamp, now):
    return max(1, int(timestamp - now + 0.999))


def _consume_request_budget(client_key, now=None):
    """Consume one request from the client and process-wide budgets.

    Returns (allowed, retry_after, scope, remaining_for_client). The
    process-wide cap is a circuit breaker, not a replacement for a shared
    provider or edge quota in a multi-instance deployment.
    """
    config = _rate_limit_config()
    current = monotonic() if now is None else now

    with _RATE_LOCK:
        while _TOTAL_REQUESTS and _TOTAL_REQUESTS[0] <= current - config["total_window"]:
            _TOTAL_REQUESTS.popleft()

        if len(_TOTAL_REQUESTS) >= config["total_limit"]:
            return (
                False,
                _seconds_until(
                    _TOTAL_REQUESTS[0] + config["total_window"], current
                ),
                "global",
                0,
            )

        bucket = _CLIENT_REQUESTS.get(client_key)
        if bucket is not None:
            while bucket and bucket[0] <= current - config["client_window"]:
                bucket.popleft()
            if not bucket:
                _CLIENT_REQUESTS.pop(client_key, None)
                bucket = None

        if bucket is None:
            if len(_CLIENT_REQUESTS) >= MAX_RATE_BUCKETS:
                return False, config["client_window"], "capacity", 0
            bucket = deque()
            _CLIENT_REQUESTS[client_key] = bucket

        if len(bucket) >= config["client_limit"]:
            return (
                False,
                _seconds_until(
                    bucket[0] + config["client_window"], current
                ),
                "client",
                0,
            )

        bucket.append(current)
        _TOTAL_REQUESTS.append(current)
        return (
            True,
            0,
            "",
            config["client_limit"] - len(bucket),
        )


def _reset_rate_limit_state():
    """Reset process-local request state; used by tests and controlled restarts."""
    with _RATE_LOCK:
        _CLIENT_REQUESTS.clear()
        _TOTAL_REQUESTS.clear()

def _allowed_origins():
    """Return production origins plus optional comma-separated deployment overrides."""
    configured = {
        origin.strip().rstrip("/")
        for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }
    return DEFAULT_ALLOWED_ORIGINS | configured

# ── Load index lazily from Cloudflare R2 ─────────────────────

R2_BASE = os.environ.get("RAG_INDEX_BASE", "https://data.projectfiner.com/rag").rstrip("/")
CHUNKS = None
BM25 = None
_INDEX_LOCK = Lock()

def _fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_index():
    """Load both index files atomically so a transient R2 error does not break import."""
    global CHUNKS, BM25
    if CHUNKS is not None and BM25 is not None:
        return

    with _INDEX_LOCK:
        if CHUNKS is not None and BM25 is not None:
            return
        chunks = _fetch_json(f"{R2_BASE}/chunks.json")
        bm25 = _fetch_json(f"{R2_BASE}/bm25_params.json")
        CHUNKS = chunks
        BM25 = bm25


# ── BM25 Search ──────────────────────────────────────────────

def tokenize(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def bm25_search(query, top_k=8, state_filter=None):
    _load_index()
    query_tokens = tokenize(query)
    idf = BM25["idf"]
    doc_tfs = BM25["doc_tfs"]
    doc_lengths = BM25["doc_lengths"]
    avg_dl = BM25["avg_dl"]
    k1 = BM25["k1"]
    b = BM25["b"]
    n_docs = BM25["n_docs"]

    # Detect if query is data-oriented (asking for numbers/stats)
    data_keywords = {"how many", "how much", "number of", "total", "count", "district wise",
                     "districtwise", "data", "statistics", "percentage", "ratio", "amount",
                     "target", "achievement", "progress", "disbursement", "outstanding",
                     "npa", "deposit", "credit", "branch", "what is the", "list"}
    q_lower = query.lower()
    is_data_query = any(kw in q_lower for kw in data_keywords)

    scores = []
    for i in range(n_docs):
        # Pre-filter by state if specified — only score matching chunks
        if state_filter and CHUNKS[i]["state"].lower() != state_filter.lower():
            continue

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

        # Boost table chunks for data-oriented queries
        if score > 0 and is_data_query and CHUNKS[i]["type"] == "table":
            score *= 1.5

        if score > 0:
            scores.append((i, score))

    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


# ── Llama Answering (Groq) ────────────────────────────────────

SYSTEM_PROMPT = """You are a knowledgeable assistant for Project FINER, a financial inclusion research platform focused on India. You answer questions based on SLBC (State Level Bankers' Committee) data — structured district-level tables, agenda booklets, and minutes of meetings.

Guidelines:
- Answer based ONLY on the provided context. If the context doesn't contain enough information, say so clearly.
- Cite specific sources: mention the state, document type (table/booklet/minutes), and quarter when referencing information.
- Use precise numbers and data when available in the context. When table data is provided, cite the actual district-level numbers.
- For financial figures, note they are typically in Rs. Lakhs (1 Lakh = Rs. 100,000).
- Keep answers concise but thorough. Use bullet points for multi-part answers.
- If the question is about a specific state, focus on that state's data.
- When "table" type sources are provided, these contain structured district-level data extracted from SLBC booklets — prefer these for quantitative questions.
- States covered: Assam, Meghalaya, Manipur, Mizoram, Nagaland, Arunachal Pradesh, Tripura, Sikkim, Bihar, West Bengal, Jharkhand, Odisha, Chhattisgarh, Karnataka, Kerala, Tamil Nadu."""


def ask_llama(question, context_chunks):
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise Exception("GROQ_API_KEY not set")

    # Build context from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        source = f"[{chunk['state']} | {chunk['type']} | {chunk['quarter']} | pages {chunk['page_start']}-{chunk['page_end']}]"
        context_parts.append(f"--- Source {i+1}: {source} ---\n{chunk['text']}")

    context = "\n\n".join(context_parts)

    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Based on the following excerpts from SLBC meeting documents, answer this question:

Question: {question}

Context:
{context}

Answer the question based on the context above. Cite the source documents when referencing specific information."""
            }
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=25) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return result["choices"][0]["message"]["content"]


# ── State Detection ───────────────────────────────────────────

STATE_NAMES = {
    "assam": "Assam",
    "meghalaya": "Meghalaya",
    "manipur": "Manipur",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "arunachal pradesh": "Arunachal Pradesh",
    "arunachal": "Arunachal Pradesh",
    "tripura": "Tripura",
    "sikkim": "Sikkim",
    "bihar": "Bihar",
    "west bengal": "West Bengal",
    "jharkhand": "Jharkhand",
    "odisha": "Odisha",
    "chhattisgarh": "Chhattisgarh",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "tamil nadu": "Tamil Nadu",
}

# Keywords that indicate a cross-state query (should NOT auto-filter)
CROSS_STATE_KEYWORDS = {"all", "across", "compare", "comparison", "every", "each", "ne states", "ne region", "north east", "northeast"}


def detect_state_in_query(question):
    """Auto-detect a single state mentioned in the query.
    Returns None if zero or multiple states found, or if cross-state keywords present."""
    q_lower = question.lower()

    # If cross-state keywords present, don't filter
    # Use word-boundary matching to avoid false positives (e.g. "especially" matching "all")
    for kw in CROSS_STATE_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', q_lower):
            return None

    # Find which states are mentioned (word-boundary match)
    found = set()
    for key, name in STATE_NAMES.items():
        if re.search(r'\b' + re.escape(key) + r'\b', q_lower):
            found.add(name)

    # Only auto-filter if exactly one state detected
    if len(found) == 1:
        return found.pop()
    return None


# ── Handler ──────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self._origin_is_allowed():
            self._respond(403, {"error": "Origin not allowed"})
            return

        if os.environ.get("ASK_API_ENABLED", "true").lower() not in {"1", "true", "yes"}:
            self._respond(503, {"error": "Answer service is temporarily unavailable"})
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._respond(415, {"error": "Content-Type must be application/json"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except (TypeError, ValueError):
            self._respond(411, {"error": "Valid Content-Length required"})
            return

        if content_length <= 0:
            self._respond(400, {"error": "Request body is required"})
            return
        if content_length > MAX_BODY_BYTES:
            self._respond(413, {"error": "Request body too large"})
            return

        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._respond(400, {"error": "Invalid JSON"})
            return

        if not isinstance(data, dict):
            self._respond(400, {"error": "JSON body must be an object"})
            return

        question_value = data.get("question", "")
        if not isinstance(question_value, str):
            self._respond(400, {"error": "'question' must be a string"})
            return

        question = question_value.strip()
        if not question:
            self._respond(400, {"error": "Missing 'question' field"})
            return

        if len(question) > 500:
            self._respond(400, {"error": "Question too long (max 500 chars)"})
            return

        allowed, retry_after, scope, remaining = _consume_request_budget(
            _request_client_key(self)
        )
        if not allowed:
            if scope == "client":
                self._respond(
                    429,
                    {"error": "Too many requests; try again later."},
                    {"Retry-After": str(retry_after)},
                )
            else:
                self._respond(
                    503,
                    {"error": "Answer service is temporarily unavailable"},
                    {"Retry-After": str(retry_after)},
                )
            return

        # Optional state filter — explicit or auto-detected from query
        state_value = data.get("state", "")
        if state_value is not None and not isinstance(state_value, str):
            self._respond(400, {"error": "'state' must be a string"})
            return
        state_filter = (state_value or "").strip() or None
        if not state_filter:
            state_filter = detect_state_in_query(question)

        # BM25 search — pre-filtered by state when applicable
        results = bm25_search(question, top_k=30, state_filter=state_filter)

        # Build context chunks
        context_chunks = []
        if state_filter:
            # Single state: results already filtered, ensure type diversity
            tables = []
            narrative = []
            for idx, score in results:
                chunk = CHUNKS[idx]
                if len(chunk["text"]) < 400:
                    continue  # Skip header-only fragments
                if chunk["type"] == "table":
                    tables.append(chunk)
                else:
                    narrative.append(chunk)
            # Interleave: prefer tables for first slots, fill with narrative
            for t in tables[:4]:
                context_chunks.append(t)
            for n in narrative[:4]:
                context_chunks.append(n)
            context_chunks = context_chunks[:6]
            if not context_chunks:
                # Fallback: just take whatever matches (even short chunks)
                for idx, score in results:
                    context_chunks.append(CHUNKS[idx])
                    if len(context_chunks) >= 6:
                        break
        else:
            # No state filter: ensure diversity across states
            seen_states = set()
            remaining = []
            for idx, score in results:
                chunk = CHUNKS[idx]
                if chunk["state"] not in seen_states:
                    context_chunks.append(chunk)
                    seen_states.add(chunk["state"])
                else:
                    remaining.append(chunk)
                if len(seen_states) >= 6:
                    break
            # Fill remaining slots with best overall
            for chunk in remaining:
                if len(context_chunks) >= 8:
                    break
                context_chunks.append(chunk)

        if not context_chunks:
            self._respond(200, {
                "answer": "I couldn't find any relevant information in the SLBC meeting documents for your question. Try rephrasing or broadening your query.",
                "sources": []
            })
            return

        # Ask Llama via Groq
        try:
            answer = ask_llama(question, context_chunks)
        except Exception as e:
            print(f"Groq request failed ({type(e).__name__}): {e}")
            self._respond(502, {"error": "Answer service is temporarily unavailable"})
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
        if not self._origin_is_allowed():
            self._respond(403, {"error": "Origin not allowed"})
            return

        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _origin_is_allowed(self):
        origin = self.headers.get("Origin")
        return not origin or origin.rstrip("/") in _allowed_origins()

    def _send_cors_headers(self):
        origin = self.headers.get("Origin")
        if origin and origin.rstrip("/") in _allowed_origins():
            self.send_header("Access-Control-Allow-Origin", origin.rstrip("/"))
            self.send_header("Vary", "Origin")

    def _respond(self, status, data, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, str(value))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
