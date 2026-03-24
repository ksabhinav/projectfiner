#!/usr/bin/env python3
"""Export PhonePe data from SQLite → phonepe_district_timeseries.json."""

import json
import os
import sqlite3
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
OUT_FILE = os.path.join(PROJECT, 'public', 'digital-payments', 'phonepe_district_timeseries.json')


def export_phonepe():
    db = sqlite3.connect(DB_PATH)

    rows = db.execute("""
        SELECT pp.district_name_raw, pp.state_slug, p.label,
               pp.transaction_count, pp.transaction_amount
        FROM phonepe_data pp
        JOIN periods p ON pp.period_id = p.id
        ORDER BY p.code, pp.state_slug, pp.district_name_raw
    """).fetchall()

    # Group by period
    periods_dict = defaultdict(list)
    for district, state_slug, period, count, amount in rows:
        periods_dict[period].append({
            'district': district,
            'period': period,
            'phonepe_upi__transaction_count': count,
            'phonepe_upi__transaction_amount': amount,
            'phonepe_upi__state': state_slug,
        })

    output = {
        'source': 'PhonePe Pulse',
        'amount_unit': 'Rs. Lakhs',
        'num_periods': len(periods_dict),
        'periods': []
    }

    MONTH_ORDER = {'March': 3, 'June': 6, 'September': 9, 'December': 12}

    for period in sorted(periods_dict.keys(),
                         key=lambda l: (int(l.split()[1]), MONTH_ORDER.get(l.split()[0], 0))):
        districts = periods_dict[period]
        output['periods'].append({
            'period': period,
            'num_districts': len(districts),
            'districts': districts,
        })

    with open(OUT_FILE, 'w') as f:
        json.dump(output, f, separators=(',', ':'))

    size = os.path.getsize(OUT_FILE) / 1024 / 1024
    print(f"PhonePe: {len(rows):,} records → {size:.1f} MB")
    print(f"Periods: {len(output['periods'])}")
    db.close()


if __name__ == '__main__':
    export_phonepe()
