"""
Shared helpers for SHRUG-derived indicator builders.

The main one is `build_finer_lookup()`, which returns a dict
keyed by `(pc11_state_id_2digit, pc11_district_id_3digit)` →
`(lgd_code, district_name, state_name)`.

Two-stage keying handles post-Census-2011 state splits:
- Telangana (lgd 36) was carved from Andhra Pradesh in June 2014.
  All pre-2014 Telangana districts sit in SHRUG under
  pc11_state_id="28" (AP). Without the alias, our join (Telangana's
  state_lgd_code=36 → "36" vs SHRUG's "28") misses them entirely.
- Ladakh (lgd 37) was carved from J&K in October 2019; same fix
  applies under pc11_state_id="01".

Pre-Census-2011 splits (Chhattisgarh from MP, Jharkhand from Bihar,
Uttarakhand from UP — all year 2000) don't need aliases because
Census 2011 already used the post-split state codes.
"""
import sqlite3
from pathlib import Path


PC11_STATE_ALIASES = {
    # current_state_lgd: [list of additional pc11_state_id strings to map under]
    36: ['28'],  # Telangana (2014) ← Andhra Pradesh (PC11 = 28)
    37: ['01'],  # Ladakh (2019) ← Jammu & Kashmir (PC11 = 01)
}


def build_finer_lookup(db_path: Path) -> dict:
    """
    Return {(pc11_state_id, pc11_district_id): (lgd, district_name, state_name)}.
    Each FINER district is registered under both its current state's PC11 code
    AND any predecessor state code that owned it in Census 2011.
    """
    db = sqlite3.connect(db_path)
    finer = {}
    rows = db.execute("""
        SELECT d.lgd_code, d.name, d.state_lgd_code, d.census_2011_code, s.name
        FROM districts d
        JOIN states s ON s.lgd_code = d.state_lgd_code
        WHERE d.census_2011_code IS NOT NULL AND d.census_2011_code != ''
    """).fetchall()
    db.close()

    for lgd, dname, st_lgd, c11, sname in rows:
        try:
            dcode = f"{int(c11):03d}"
        except (ValueError, TypeError):
            continue
        entry = (lgd, dname, sname)
        primary_key = (f"{st_lgd:02d}", dcode)
        finer[primary_key] = entry
        for alias_st in PC11_STATE_ALIASES.get(st_lgd, []):
            finer[(alias_st, dcode)] = entry
    return finer
