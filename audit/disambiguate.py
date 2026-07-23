"""Header disambiguation for FINER quarterly ACP extracts.

Root cause it fixes: raw quarterly CSVs carry target/achievement/% triplets
where the achievement and % columns share bare, repeated names (a, pct, amt,
no, achv_no, ...). When a row is stored as a dict keyed by column name
(_complete.json), duplicate keys overwrite and only the LAST triplet (the grand
total) survives. Disambiguating the headers BEFORE dict-ifying preserves every
per-subcategory value. State-agnostic: it keys off duplication, not a hardcoded
token list, so it covers Odisha (a/pct), Bihar (amt/Amt/...), Jharkhand (amt/no).
"""
from collections import Counter


def disambiguate_headers(headers):
    """Prefix each duplicated column with its nearest preceding unique
    (anchor) column, so a/pct/amt attach to the subcategory they describe.
    Returns a new list, same length and order."""
    counts = Counter(headers)
    dup = {h for h, c in counts.items() if c > 1}
    out, anchor, seen = [], None, Counter()
    for h in headers:
        if h in dup:
            base = anchor or "col"
            base = base[:-2] if base.endswith("_t") else base
            name = f"{base}_{h}"
            seen[name] += 1
            if seen[name] > 1:          # guard against collisions
                name = f"{name}{seen[name]}"
            out.append(name)
        else:
            anchor = h
            out.append(h)
    return out


def row_to_dict(headers, values):
    """Positional CSV row -> dict with NO collapse. Use csv.reader (not
    DictReader) upstream so raw duplicate headers reach here intact."""
    return dict(zip(disambiguate_headers(headers), values))
