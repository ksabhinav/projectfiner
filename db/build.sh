#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=========================================="
echo " FINER Database Build Pipeline"
echo "=========================================="
echo ""

# Remove old database for clean rebuild
if [ "$1" = "--clean" ]; then
    rm -f finer.db
    echo "Cleaned old database."
fi

echo "=== 1. Initializing schema ==="
python3 init_schema.py

echo ""
echo "=== 2. Importing reference data (states, districts, aliases) ==="
python3 import_reference.py

echo ""
echo "=== 3. Importing SLBC data (22 states) ==="
python3 import_slbc.py

echo ""
echo "=== 4. Importing PhonePe Pulse data ==="
python3 import_phonepe.py

echo ""
echo "=== 5. Importing NFHS-5 data ==="
python3 import_nfhs.py

echo ""
echo "=== 6. Importing Aadhaar enrollment data ==="
python3 import_aadhaar.py

echo ""
echo "=========================================="
echo " Database Summary"
echo "=========================================="
python3 -c "
import sqlite3, os
db = sqlite3.connect('finer.db')
tables = ['states', 'districts', 'district_aliases', 'periods', 'slbc_fields', 'slbc_data', 'phonepe_data', 'nfhs_indicators', 'nfhs_data', 'aadhaar_enrollment', 'import_log']
for t in tables:
    try:
        n = db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'  {t:25s} {n:>12,} rows')
    except: pass
size = os.path.getsize('finer.db') / 1024 / 1024
print(f'\n  Database size: {size:.1f} MB')
db.close()
"

echo ""
echo "=== Done! ==="
