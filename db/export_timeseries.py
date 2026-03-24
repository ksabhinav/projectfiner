#!/usr/bin/env python3
"""Export SLBC data from SQLite → {state}_fi_timeseries.json files.

Produces JSON identical to the current format consumed by TrendTracker and DataExplorer.
"""

import json
import os
import sqlite3
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
SLBC_DIR = os.path.join(PROJECT, 'public', 'slbc-data')

# Month ordering for period sorting
MONTH_ORDER = {
    'March': 3, 'June': 6, 'September': 9, 'December': 12,
    'January': 1, 'February': 2, 'April': 4, 'May': 5,
    'July': 7, 'August': 8, 'October': 10, 'November': 11,
}


def sort_period_key(label):
    """Sort key for period labels like 'June 2020'."""
    parts = label.split()
    if len(parts) == 2:
        month, year = parts
        return (int(year), MONTH_ORDER.get(month, 0))
    return (0, 0)


def export_state(db, state_lgd, slug, slim=False):
    """Export one state's data to timeseries JSON."""

    # Category filter for slim version
    slim_prefixes = None
    if slim:
        slim_prefixes = (
            'credit_deposit_ratio', 'pmjdy', 'branch_network', 'kcc',
            'shg', 'digital_transactions', 'aadhaar_authentication',
            'social_security', 'pmegp', 'housing_pmay', 'sui',
            'sc_st_finance', 'women_finance', 'education_loan', 'pmmy_mudra',
        )

    # Query all data for this state
    query = """
        SELECT d.name as district, p.label as period, sf.field_key, sd.value_text
        FROM slbc_data sd
        JOIN districts d ON sd.district_lgd = d.lgd_code
        JOIN periods p ON sd.period_id = p.id
        JOIN slbc_fields sf ON sd.field_id = sf.id
        WHERE sd.state_lgd_code = ?
        ORDER BY p.code, d.name, sf.field_key
    """
    rows = db.execute(query, (state_lgd,)).fetchall()

    if not rows:
        return 0

    # Group by period → district → {field: value}
    periods_dict = defaultdict(lambda: defaultdict(dict))
    for district, period, field_key, value_text in rows:
        if slim and slim_prefixes:
            category = field_key.split('__')[0] if '__' in field_key else ''
            # Check if category matches any slim prefix (including numbered variants)
            base_cat = category.rstrip('0123456789').rstrip('_p').rstrip('_')
            if base_cat not in slim_prefixes and category not in slim_prefixes:
                continue
        periods_dict[period][district][field_key] = value_text

    # Build output structure
    output = {
        'source': f'SLBC {slug.replace("-", " ").title()}',
        'state': slug,
        'periods': []
    }

    for period in sorted(periods_dict.keys(), key=sort_period_key):
        districts_list = []
        for district in sorted(periods_dict[period].keys()):
            rec = {'district': district, 'period': period}
            rec.update(periods_dict[period][district])
            districts_list.append(rec)

        output['periods'].append({
            'period': period,
            'districts': districts_list,
        })

    # Write JSON
    suffix = '_fi_slim.json' if slim else '_fi_timeseries.json'
    out_path = os.path.join(SLBC_DIR, slug, f'{slug}{suffix}')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if slim:
        # Slim uses compact separators
        with open(out_path, 'w') as f:
            json.dump(output, f, separators=(',', ':'))
    else:
        with open(out_path, 'w') as f:
            json.dump(output, f, indent=2)

    return len(rows)


def export_all(slim=False):
    db = sqlite3.connect(DB_PATH)

    # Get all states with SLBC data
    states = db.execute("""
        SELECT DISTINCT s.lgd_code, s.slug
        FROM states s
        JOIN slbc_data sd ON s.lgd_code = sd.state_lgd_code
        ORDER BY s.slug
    """).fetchall()

    label = "slim" if slim else "timeseries"
    total = 0

    for state_lgd, slug in states:
        rows = export_state(db, state_lgd, slug, slim=slim)
        if rows > 0:
            suffix = '_fi_slim.json' if slim else '_fi_timeseries.json'
            size = os.path.getsize(os.path.join(SLBC_DIR, slug, f'{slug}{suffix}')) / 1024 / 1024
            print(f"  {slug}: {rows:,} rows → {size:.1f} MB")
            total += rows

    print(f"\nTotal {label}: {total:,} rows across {len(states)} states")
    db.close()


if __name__ == '__main__':
    import sys
    if '--slim' in sys.argv:
        print("=== Exporting slim timeseries ===")
        export_all(slim=True)
    else:
        print("=== Exporting full timeseries ===")
        export_all(slim=False)
        print("\n=== Exporting slim timeseries ===")
        export_all(slim=True)
