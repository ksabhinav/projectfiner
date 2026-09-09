"""Shared, non-destructive write primitives for FINER's SLBC importers."""

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


def upsert_slbc_data(db, rows):
    """Insert new observations and update conflicts without replacing row IDs.

    SQLite's INSERT OR REPLACE deletes the existing row before inserting a new
    one. This helper uses an explicit conflict rule so references to
    slbc_data.id remain valid and repeated imports converge on the same
    database state.
    """
    rows = list(rows)
    if not rows:
        return 0
    db.executemany(SLBC_UPSERT_SQL, rows)
    return len(rows)
