"""History-preserving helpers for state SLBC extractors."""

import json
from pathlib import Path


def merge_complete_history(candidate, output_path):
    """Merge extracted quarters over an existing complete.json artifact.

    The current extraction wins for the quarters it contains. Quarters absent
    from the local source set are retained, including Wayback-recovered history
    that cannot be recreated by a live-site rerun.
    """
    output_path = Path(output_path)
    candidate = dict(candidate)
    candidate_quarters = dict(candidate.get("quarters", {}))
    preexisting_quarters = {}

    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        preexisting_quarters = dict(existing.get("quarters", {}))
        merged = dict(existing)
        merged.update({key: value for key, value in candidate.items() if key != "quarters"})
    else:
        merged = candidate

    quarters = dict(preexisting_quarters)
    quarters.update(candidate_quarters)
    merged["quarters"] = dict(sorted(quarters.items()))

    lost = set(preexisting_quarters) - set(merged["quarters"])
    if lost:
        raise RuntimeError(
            "Refusing to shrink extractor history; missing quarters: "
            + ", ".join(sorted(lost))
        )

    return merged, {
        "preexisting": len(preexisting_quarters),
        "extracted": len(candidate_quarters),
        "added": len(set(candidate_quarters) - set(preexisting_quarters)),
        "retained": len(set(preexisting_quarters) - set(candidate_quarters)),
        "total": len(merged["quarters"]),
    }
