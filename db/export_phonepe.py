#!/usr/bin/env python3
"""Export PhonePe partition metadata from SQLite.

Quarter payloads are produced by export_indicator_files.py; the top-level file
is deliberately a small manifest so clients never fetch the complete history.
"""

import json
import os
import sqlite3
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
OUT_FILE = os.path.join(PROJECT, 'public', 'digital-payments', 'phonepe_district_timeseries.json')

PHONEPE_SOURCE_URL = 'https://github.com/PhonePe/pulse'
PHONEPE_SOURCE_REVISION = '943e6e52a71513d683f804add12d0b61145e8007'
PHONEPE_LICENSE = 'CDLA-Permissive-2.0'
PHONEPE_METHODOLOGY = 'phonepe-pulse-restated-amj-2026'
PHONEPE_COMPARABILITY_WARNING = (
    'PhonePe restated all periods from January-March 2018. Do not join these '
    'figures to previously downloaded Pulse series or interpret the restatement '
    'boundary as growth.'
)


def export_phonepe():
    db = sqlite3.connect(DB_PATH)

    rows = db.execute("""
        SELECT pp.district_name_raw, pp.state_slug, p.label,
               pp.transaction_count, pp.transaction_amount, pp.registered_merchants
        FROM phonepe_data pp
        JOIN periods p ON pp.period_id = p.id
        ORDER BY p.code, pp.state_slug, pp.district_name_raw
    """).fetchall()

    # Group by period
    periods_dict = defaultdict(list)
    for district, state_slug, period, count, amount, merchants in rows:
        periods_dict[period].append({
            'district': district,
            'period': period,
            'phonepe_upi__transaction_count': count,
            'phonepe_upi__transaction_amount': amount,
            'phonepe_upi__registered_merchants': merchants,
            'phonepe_upi__state': state_slug,
        })

    output = {
        'schema_version': 3,
        'storage': 'quarterly-partitions',
        'source': 'PhonePe Pulse',
        'source_url': PHONEPE_SOURCE_URL,
        'source_revision': PHONEPE_SOURCE_REVISION,
        'license': PHONEPE_LICENSE,
        'amount_unit': 'Rs. Lakhs',
        'methodology_version': PHONEPE_METHODOLOGY,
        'comparability_warning': PHONEPE_COMPARABILITY_WARNING,
        'num_periods': len(periods_dict),
        'num_district_periods': len(rows),
        'latest_period': None,
        'periods': []
    }

    MONTH_ORDER = {'March': 3, 'June': 6, 'September': 9, 'December': 12}

    for period in sorted(periods_dict.keys(),
                         key=lambda l: (int(l.split()[1]), MONTH_ORDER.get(l.split()[0], 0))):
        districts = periods_dict[period]
        month = MONTH_ORDER.get(period.split()[0], 0)
        period_code = f"{period.split()[1]}-{month:02d}"
        output['periods'].append({
            'period': period,
            'period_code': period_code,
            'num_districts': len(districts),
            'path': f'../indicators/digital_transactions/{period_code}.json',
        })

    if output['periods']:
        output['latest_period'] = output['periods'][-1]['period_code']

    with open(OUT_FILE, 'w') as f:
        json.dump(output, f, separators=(',', ':'))

    size = os.path.getsize(OUT_FILE) / 1024 / 1024
    print(f"PhonePe: {len(rows):,} records → {size:.1f} MB")
    print(f"Periods: {len(output['periods'])}")
    db.close()


if __name__ == '__main__':
    export_phonepe()
