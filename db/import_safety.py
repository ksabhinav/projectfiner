"""Shared safety primitives for FINER's SLBC importers."""

import hashlib
import json
import os
import re
from pathlib import Path


SLBC_UPSERT_SQL = """
INSERT INTO slbc_data (
    state_lgd_code,
    district_lgd,
    period_id,
    field_id,
    value_text,
    value_numeric,
    source_file
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(district_lgd, period_id, field_id) DO UPDATE SET
    state_lgd_code = excluded.state_lgd_code,
    value_text = excluded.value_text,
    value_numeric = excluded.value_numeric,
    source_file = excluded.source_file
"""

DEFAULT_REJECT_DIR = Path(
    os.environ.get(
        "FINER_REJECT_DIR",
        Path(__file__).resolve().parent / "import-rejects",
    )
)


def upsert_slbc_data(db, rows):
    """Insert new observations and update conflicts without replacing row IDs."""
    rows = list(rows)
    if not rows:
        return 0
    db.executemany(SLBC_UPSERT_SQL, rows)
    return len(rows)


class ImportAudit:
    """Reconcile source records and persist deterministic reject evidence."""

    def __init__(self, source):
        self.source = source
        self.observed = 0
        self.accepted = 0
        self.rejected = 0
        self._rejects = {}

    def accept(self):
        self.observed += 1
        self.accepted += 1

    def reject(self, reason, *, state_slug=None, period_label=None, district_raw=None):
        self.observed += 1
        self.rejected += 1
        identity = {
            "source": self.source,
            "state_slug": state_slug,
            "period_label": period_label,
            "district_raw": district_raw,
            "reason": reason,
        }
        canonical = json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        entry = self._rejects.setdefault(
            fingerprint,
            {**identity, "fingerprint": fingerprint, "occurrence_count": 0},
        )
        entry["occurrence_count"] += 1

    def summary(self):
        self._assert_reconciled()
        return {
            "source": self.source,
            "records_observed": self.observed,
            "records_accepted": self.accepted,
            "records_rejected": self.rejected,
            "unique_rejects": len(self._rejects),
        }

    def write(self, directory=DEFAULT_REJECT_DIR):
        """Atomically replace the current reject ledger and reconciliation summary."""
        self._assert_reconciled()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^a-z0-9._-]+", "-", self.source.lower()).strip("-")
        ledger_path = directory / f"{stem}.jsonl"
        summary_path = directory / f"{stem}.summary.json"
        ledger = "".join(
            json.dumps(self._rejects[key], ensure_ascii=False, sort_keys=True) + "\n"
            for key in sorted(self._rejects)
        )
        self._atomic_write(ledger_path, ledger)
        self._atomic_write(
            summary_path,
            json.dumps(self.summary(), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )
        return ledger_path, summary_path

    def _assert_reconciled(self):
        if self.observed != self.accepted + self.rejected:
            raise RuntimeError(
                "Import audit does not reconcile: "
                f"{self.observed} observed != {self.accepted} accepted "
                f"+ {self.rejected} rejected"
            )

    @staticmethod
    def _atomic_write(path, content):
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
