#!/usr/bin/env python3
"""Import Jammu & Kashmir SLBC data → slbc_data table.

Reads slbc-data/jammu-kashmir/jammu-kashmir_fi_timeseries.json and writes one
row per (district, period, field) using INSERT OR REPLACE.

Mirrors the Ladakh import pattern: J&K state_lgd_code = 1.
Field IDs used (same as Ladakh):
  22 = credit_deposit_ratio__total_deposit   (Lakhs)
  23 = credit_deposit_ratio__total_advance   (Lakhs)
 1228 = credit_deposit_ratio__cd_ratio       (percent)
   39 = branch_network__total_branch         (count)
Plus 'credit_deposit_ratio__gross_npa' if a field row exists in slbc_fields.

Period codes (YYYY-MM) are resolved against the `periods` table by code.

District names are resolved via the `districts` table (state_lgd_code=1).
"""
import json
import os
import sqlite3
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
DB = os.path.join(HERE, 'finer.db')
SRC = os.path.join(ROOT, 'slbc-data', 'jammu-kashmir', 'jammu-kashmir_fi_timeseries.json')

STATE_LGD = 1
SOURCE_FILE = 'jammu-kashmir_fi_timeseries.json'

# Period label → code  (same convention as periods table)
LABEL_TO_CODE = {
    'September 2022': '2022-09',
    'September 2023': '2023-09',
    'December 2023':  '2023-12',
    'March 2024':     '2024-03',
    'March 2025':     '2025-03',
    'December 2025':  '2025-12',
}


def get_or_create_field(conn, field_key, category, name, unit):
    cur = conn.execute('SELECT id FROM slbc_fields WHERE field_key = ?', (field_key,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        'INSERT INTO slbc_fields(field_key, category, field_name, unit) VALUES (?,?,?,?)',
        (field_key, category, name, unit),
    )
    return cur.lastrowid


def main():
    if not os.path.exists(SRC):
        sys.exit(f'Source file not found: {SRC}')
    if not os.path.exists(DB):
        sys.exit(f'DB not found: {DB}')

    with open(SRC) as f:
        ts = json.load(f)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Build period code → id map
    periods = {row[1]: row[0] for row in cur.execute('SELECT id, code FROM periods')}
    # Build district name (case-insensitive) → lgd_code map for J&K
    districts = {row[1].strip().lower(): row[0]
                 for row in cur.execute('SELECT lgd_code, name FROM districts WHERE state_lgd_code = ?', (STATE_LGD,))}

    # Field IDs (per Ladakh import). Get or create with proper category/unit.
    field_ids = {
        'credit_deposit_ratio__total_deposit':  get_or_create_field(conn, 'credit_deposit_ratio__total_deposit', 'credit_deposit_ratio', 'total_deposit', 'lakhs'),
        'credit_deposit_ratio__total_advance':  get_or_create_field(conn, 'credit_deposit_ratio__total_advance', 'credit_deposit_ratio', 'total_advance', 'lakhs'),
        'credit_deposit_ratio__cd_ratio':       get_or_create_field(conn, 'credit_deposit_ratio__cd_ratio',       'credit_deposit_ratio', 'cd_ratio',       'percent'),
        'branch_network__total_branch':         get_or_create_field(conn, 'branch_network__total_branch',         'branch_network',       'total_branch',   'count'),
        'credit_deposit_ratio__gross_npa':      get_or_create_field(conn, 'credit_deposit_ratio__gross_npa',      'credit_deposit_ratio', 'gross_npa',      'lakhs'),
    }

    # Wipe any prior J&K rows from the same source file (idempotent)
    cur.execute('DELETE FROM slbc_data WHERE state_lgd_code = ? AND source_file = ?',
                (STATE_LGD, SOURCE_FILE))

    inserted = 0
    skipped_district = 0
    skipped_period = 0
    for period in ts['periods']:
        label = period['period']
        qcode = LABEL_TO_CODE.get(label)
        if qcode is None or qcode not in periods:
            skipped_period += 1
            continue
        period_id = periods[qcode]
        for row in period['districts']:
            dname = row['district']
            dlgd = districts.get(dname.strip().lower())
            if dlgd is None:
                skipped_district += 1
                continue
            for field_key, fid in field_ids.items():
                if field_key not in row or row[field_key] is None:
                    continue
                val = row[field_key]
                cur.execute(
                    'INSERT OR REPLACE INTO slbc_data(state_lgd_code, district_lgd, period_id, field_id, value_text, value_numeric, source_file) VALUES (?,?,?,?,?,?,?)',
                    (STATE_LGD, dlgd, period_id, fid, str(val), float(val) if isinstance(val, (int, float)) else None, SOURCE_FILE),
                )
                inserted += 1

    conn.commit()
    print(f'J&K import: {inserted} rows inserted; skipped districts={skipped_district}, periods={skipped_period}')

    # Quick verification
    n = cur.execute('SELECT COUNT(*) FROM slbc_data WHERE state_lgd_code = ?', (STATE_LGD,)).fetchone()[0]
    print(f'Total J&K rows in slbc_data now: {n}')
    print('Sample:')
    for r in cur.execute('''
        SELECT d.name, p.label, sf.field_key, sd.value_numeric
        FROM slbc_data sd
        JOIN districts d ON d.lgd_code = sd.district_lgd
        JOIN periods p ON p.id = sd.period_id
        JOIN slbc_fields sf ON sf.id = sd.field_id
        WHERE sd.state_lgd_code = ?
        ORDER BY p.code DESC, d.name
        LIMIT 12
    ''', (STATE_LGD,)):
        print(' ', r)

    conn.close()


if __name__ == '__main__':
    main()
