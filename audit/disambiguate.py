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


def disambiguate_headers_keep_last(headers):
    """Backward-compatible variant: the LAST occurrence of each duplicated name
    KEEPS its original name (matching the incumbent dict-collapse, which retained
    the last value), while the earlier, previously-dropped occurrences are
    recovered under anchor-prefixed names. Use this when a duplicated column is
    also a canonical field that downstream code looks up by name (e.g. a state
    where `cd_ratio` itself repeats) — the repair then only ADDS the lost columns
    and never removes the canonical name. New names are guaranteed unique against
    the full header set and each other."""
    counts = Counter(headers)
    dup = {h for h, c in counts.items() if c > 1}
    last_idx = {h: i for i, h in enumerate(headers) if h in dup}   # last wins
    existing = set(headers)
    out, anchor, used = [], None, set()
    for i, h in enumerate(headers):
        if h in dup and i != last_idx[h]:
            base = anchor or "col"
            base = base[:-2] if base.endswith("_t") else base
            name = f"{base}_{h}"
            k = 1
            while name in existing or name in used:      # collision-proof
                k += 1
                name = f"{base}_{h}_{k}"
            used.add(name)
            out.append(name)
        else:                                            # unique, or last of a dup
            if h not in dup:
                anchor = h
            out.append(h)
    return out


def row_to_dict(headers, values):
    """Positional CSV row -> dict with NO collapse. Use csv.reader (not
    DictReader) upstream so raw duplicate headers reach here intact."""
    return dict(zip(disambiguate_headers(headers), values))
