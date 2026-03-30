#!/usr/bin/env python3
"""Export NRLM SHG district data from SQLite → public/nrlm/shg_district.json.

Output format:
{
  "districts": [
    {
      "lgd": "123",
      "district": "DISTRICT NAME",
      "state": "STATE NAME",
      "shg_total": 12345,
      "members_total": 123456,
      "shg_new": 1000,
      "shg_revived": 500,
      "shg_prenrlm": 10845
    },
    ...
  ]
}
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'finer.db')
PROJECT = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(PROJECT, 'public', 'nrlm')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'shg_district.json')


def export_nrlm():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # Check table exists
    exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='nrlm_shg'"
    ).fetchone()
    if not exists:
        print("ERROR: nrlm_shg table not found. Run import_nrlm.py first.")
        return

    # Query joined with districts for canonical name
    rows = db.execute("""
        SELECT
            n.lgd_code,
            COALESCE(d.name, n.district_raw) AS district_name,
            n.district_raw,
            n.state_raw,
            n.shg_new,
            n.shg_revived,
            n.shg_prenrlm,
            n.shg_total,
            n.members_total,
            n.scraped_date
        FROM nrlm_shg n
        LEFT JOIN districts d ON n.lgd_code = d.lgd_code
        ORDER BY n.state_raw, district_name
    """).fetchall()

    db.close()

    districts = []
    for r in rows:
        entry = {
            "lgd": str(r["lgd_code"]) if r["lgd_code"] is not None else None,
            "district": r["district_name"],
            "district_raw": r["district_raw"],
            "state": r["state_raw"],
            "shg_total": r["shg_total"],
            "members_total": r["members_total"],
            "shg_new": r["shg_new"],
            "shg_revived": r["shg_revived"],
            "shg_prenrlm": r["shg_prenrlm"],
        }
        districts.append(entry)

    output = {
        "meta": {
            "source": "NRLM G1 Report",
            "portal": "https://nrlm.gov.in/shgOuterReports.do",
            "scraped_date": rows[0]["scraped_date"] if rows else None,
            "total_districts": len(districts),
            "lgd_matched": sum(1 for d in districts if d["lgd"] is not None),
        },
        "districts": districts,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"Exported {len(districts)} districts to: {OUTPUT_FILE} ({size_kb:.1f} KB)")
    print(f"LGD-matched: {output['meta']['lgd_matched']} / {output['meta']['total_districts']}")

    # Print a sample
    print("\nSample records:")
    for d in districts[:5]:
        print(f"  lgd={d['lgd']} | {d['district']} ({d['state']}) | total={d['shg_total']:,} | members={d['members_total']:,}")


if __name__ == '__main__':
    export_nrlm()
