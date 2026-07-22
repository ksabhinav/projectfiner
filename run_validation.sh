#!/bin/bash
# Run data validation after extraction
# Usage: ./run_validation.sh [state_slug]
# Exit code: 0 if no critical issues, 1 if critical issues found

# NOTE: deliberately no `set -e`. validate_data.py exits 1 when it finds
# critical issues — that is its designed signal, not a script failure. Under
# `set -e` the script died on that exit and the warning below never printed,
# so the one guard rail in the repo swallowed its own alarm.
cd "$(dirname "$0")" || exit 2

if [ -n "$1" ]; then
    echo "Validating $1..."
    python3 validate_data.py --state "$1" --verbose
else
    echo "Validating all states..."
    python3 validate_data.py --verbose
fi

exit_code=$?
if [ $exit_code -eq 1 ]; then
    echo ""
    echo "⚠ CRITICAL ISSUES FOUND — review DATA_VALIDATION_REPORT.md before committing"
fi
exit $exit_code
