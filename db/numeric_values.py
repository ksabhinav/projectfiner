"""Shared syntax rules for unreviewed source cells; no unit inference."""

import math
import re

# Accept plain decimals and correctly grouped Western or Indian thousands.
# Blind comma removal would turn malformed values such as '1,2,3' into 123.
NUMERIC_LIKE = re.compile(
    r"^[+-]?(?:(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|"
    r"[0-9]{1,2}(?:,[0-9]{2})+,[0-9]{3})(?:\.[0-9]*)?|\.[0-9]+)$"
)
MISSING_MARKERS = {"_", "-", "NA", "N/A"}
FORMULA_ERRORS = {
    "#DIV/0!", "#N/A", "#VALUE!", "#REF!", "#NAME?", "#NUM!",
    "#NULL!", "#SPILL!", "#CALC!",
}


def classify_value(value):
    """Describe cell syntax without assigning units or interpreting missingness."""
    if value is None:
        return "null"
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return "unsupported-type"
    if isinstance(value, (int, float)):
        return "numeric" if isinstance(value, int) or math.isfinite(value) else "non-finite"
    raw = value.strip()
    if not raw:
        return "blank"
    if raw.upper() in MISSING_MARKERS:
        return "missing-marker"
    if raw.upper() in FORMULA_ERRORS:
        return "spreadsheet-error"
    if raw.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf",
                        "infinity", "+infinity", "-infinity"}:
        return "non-finite"
    if NUMERIC_LIKE.fullmatch(raw):
        return "numeric"
    if raw.endswith("%") and NUMERIC_LIKE.fullmatch(raw[:-1].strip()):
        return "percentage-text"
    tokens = raw.split()
    if len(tokens) > 1 and all(NUMERIC_LIKE.fullmatch(token) for token in tokens):
        return "split-numeric-tokens"
    if "," in raw and NUMERIC_LIKE.fullmatch(raw.replace(",", "")):
        return "invalid-numeric-grouping"
    return "text"


def parse_number(value):
    """Return a finite number or None, without stripping units or guessing tokens."""
    if classify_value(value) != "numeric":
        return None
    try:
        number = float(str(value).strip().replace(",", ""))
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None
