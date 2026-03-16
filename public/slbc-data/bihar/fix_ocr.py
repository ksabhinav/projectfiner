#!/usr/bin/env python3
"""Fix OCR artifacts in Bihar SLBC data files."""

import json
import csv
import os
import re
from pathlib import Path

BASE = Path("/Users/abhinav/Downloads/projectfiner/public/slbc-data/bihar")

# ── 1. Broken word replacements (applied to field/key names only) ──
# Order matters: longer patterns first to avoid partial matches
FIELD_REPLACEMENTS = [
    # Spaced-out letters
    ("activation_as_on_30_11_2025_n_u_m_ber_of_accounts", "activation_number_of_accounts"),
    ("total_settlement_as_on_30_11_2025_n_u_m_ber_of_accounts", "total_settlement_number_of_accounts"),
    # Broken words - specific long forms first
    ("applicatio_ns_accepted", "applications_accepted"),
    ("applicatio_ns_received", "applications_received"),
    ("constructi_on_started_yes_no", "construction_started_yes_no"),
    ("nominati_ons_done_in_pmjdy_acc", "nominations_done_in_pmjdy_acc"),
    ("nomination_s_done_in_pmjdy_acc", "nominations_done_in_pmjdy_acc"),
    ("nomination_s_done_other_than_pmjdy_acc", "nominations_done_other_than_pmjdy_acc"),
    ("gram_panchay_at_covered", "gram_panchayat_covered"),
    ("total_gram_pancha_yat", "total_gram_panchayat"),
    ("programm_es_organised", "programmes_organised"),
    ("reimburseme_nt_claim_pending", "reimbursement_claim_pending"),
    ("total_rejected_r_eturned", "total_rejected_returned"),
    ("rejected_r_eturned", "rejected_returned"),
    ("export_credit_targe_t", "export_credit_target"),
    # Generic broken words (these catch remaining occurrences)
    ("disburseme_nt", "disbursement"),
    ("disbursem_ent", "disbursement"),
    ("disburse_ment", "disbursement"),
    ("sanctione_d", "sanctioned"),
    ("sanctio_n", "sanction"),
    ("administra_tion", "administration"),
    ("administr_ation", "administration"),
    # Typos
    ("husbandary", "husbandry"),
    ("fishries", "fisheries"),
]

# For n_u_m_ber that might appear in other contexts
N_U_M_BER_RE = re.compile(r'n_u_m_ber')

def fix_field_name(name):
    """Apply all OCR fixes to a single field/key name."""
    original = name
    for old, new in FIELD_REPLACEMENTS:
        if old in name:
            name = name.replace(old, new)
    # Catch any remaining n_u_m_ber
    name = N_U_M_BER_RE.sub('number', name)
    return name

def fix_field_name_changed(name):
    """Return (fixed_name, changed_bool)."""
    fixed = fix_field_name(name)
    return fixed, fixed != name


# ── Stats tracking ──
stats = {"field_renames": 0, "categories_deleted": 0, "files_modified": set()}


# ── 2. Fix bihar_complete.json ──
def fix_complete_json():
    path = BASE / "bihar_complete.json"
    with open(path) as f:
        data = json.load(f)

    changed = False
    quarters_to_check = list(data["quarters"].keys())

    for qkey in quarters_to_check:
        quarter = data["quarters"][qkey]
        tables = quarter["tables"]

        # Delete rseti_2 and rseti_4
        for bad_cat in ["rseti_2", "rseti_4"]:
            if bad_cat in tables:
                del tables[bad_cat]
                stats["categories_deleted"] += 1
                changed = True
                print(f"  Deleted {bad_cat} from quarter {qkey}")

        # Fix field names in remaining tables
        for cat_name, cat_data in tables.items():
            # Fix fields array
            new_fields = []
            for f in cat_data["fields"]:
                fixed, was_changed = fix_field_name_changed(f)
                if was_changed:
                    stats["field_renames"] += 1
                    changed = True
                new_fields.append(fixed)
            cat_data["fields"] = new_fields

            # Fix district data keys
            for dist_name, dist_data in cat_data["districts"].items():
                new_dist = {}
                for k, v in dist_data.items():
                    fixed, was_changed = fix_field_name_changed(k)
                    if was_changed:
                        stats["field_renames"] += 1
                        changed = True
                    new_dist[fixed] = v
                cat_data["districts"][dist_name] = new_dist

    if changed:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        stats["files_modified"].add(str(path))
        print(f"  Wrote {path}")


# ── 3. Fix bihar_fi_timeseries.json ──
def fix_timeseries_json():
    path = BASE / "bihar_fi_timeseries.json"
    with open(path) as f:
        data = json.load(f)

    changed = False
    for period_obj in data["periods"]:
        for dist in period_obj["districts"]:
            keys = list(dist.keys())
            for k in keys:
                # Also remove rseti_2__ and rseti_4__ prefixed keys
                if k.startswith("rseti_2__") or k.startswith("rseti_4__"):
                    del dist[k]
                    stats["field_renames"] += 1
                    changed = True
                    continue
                fixed, was_changed = fix_field_name_changed(k)
                if was_changed:
                    dist[fixed] = dist.pop(k)
                    stats["field_renames"] += 1
                    changed = True

    if changed:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        stats["files_modified"].add(str(path))
        print(f"  Wrote {path}")


# ── 4. Fix bihar_fi_timeseries.csv ──
def fix_timeseries_csv():
    path = BASE / "bihar_fi_timeseries.csv"
    with open(path, newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return

    header = rows[0]
    new_header = []
    changed = False
    cols_to_remove = set()

    for i, h in enumerate(header):
        # Remove rseti_2__ and rseti_4__ columns
        if h.startswith("rseti_2__") or h.startswith("rseti_4__"):
            cols_to_remove.add(i)
            changed = True
            stats["field_renames"] += 1
            continue
        fixed, was_changed = fix_field_name_changed(h)
        if was_changed:
            stats["field_renames"] += 1
            changed = True
        new_header.append(fixed)

    if changed:
        # Rebuild rows removing deleted columns
        new_rows = [new_header]
        for row in rows[1:]:
            new_row = [v for i, v in enumerate(row) if i not in cols_to_remove]
            new_rows.append(new_row)

        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(new_rows)
        stats["files_modified"].add(str(path))
        print(f"  Wrote {path}")


# ── 5. Fix quarterly CSVs ──
def fix_quarterly_csvs():
    quarterly_dir = BASE / "quarterly"
    if not quarterly_dir.exists():
        return

    for quarter_dir in sorted(quarterly_dir.iterdir()):
        if not quarter_dir.is_dir():
            continue

        # Delete rseti_2.csv and rseti_4.csv
        for bad_csv in ["rseti_2.csv", "rseti_4.csv"]:
            bad_path = quarter_dir / bad_csv
            if bad_path.exists():
                bad_path.unlink()
                stats["categories_deleted"] += 1
                stats["files_modified"].add(str(bad_path))
                print(f"  Deleted {bad_path}")

        # Fix headers in remaining CSVs
        for csv_path in sorted(quarter_dir.glob("*.csv")):
            try:
                with open(csv_path, newline='') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
            except Exception as e:
                print(f"  Warning: could not read {csv_path}: {e}")
                continue

            if not rows:
                continue

            header = rows[0]
            new_header = []
            changed = False
            for h in header:
                fixed, was_changed = fix_field_name_changed(h)
                if was_changed:
                    stats["field_renames"] += 1
                    changed = True
                new_header.append(fixed)

            if changed:
                rows[0] = new_header
                with open(csv_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                stats["files_modified"].add(str(csv_path))
                print(f"  Fixed headers in {csv_path.name} ({quarter_dir.name})")


# ── Main ──
if __name__ == "__main__":
    print("=== Fixing bihar_complete.json ===")
    fix_complete_json()

    print("\n=== Fixing bihar_fi_timeseries.json ===")
    fix_timeseries_json()

    print("\n=== Fixing bihar_fi_timeseries.csv ===")
    fix_timeseries_csv()

    print("\n=== Fixing quarterly CSVs ===")
    fix_quarterly_csvs()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total field renames applied: {stats['field_renames']}")
    print(f"Categories/files deleted:    {stats['categories_deleted']}")
    print(f"Files modified:              {len(stats['files_modified'])}")
    for f in sorted(stats["files_modified"]):
        print(f"  - {f}")
