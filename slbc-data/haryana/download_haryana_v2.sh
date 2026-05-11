#!/bin/bash
# Bulk download Haryana SLBC meeting annexures (131st-175th).
# Downloads into slbc-data/haryana/raw/ as {meeting_no}.{zip|rar}.
# Skips files already present.
#
# Mix of ZIP + RAR. RAR archives are extracted with `unar` (Homebrew).
set -u
cd "$(dirname "$0")"
mkdir -p raw

audit_file="meetings_audit.txt"

grep -E '^[0-9]+ \|' "$audit_file" | while IFS='|' read -r meeting_no meeting_date qlabel qcode url; do
  meeting_no=$(echo "$meeting_no" | xargs)
  url=$(echo "$url" | xargs)
  ext="${url##*.}"
  out="raw/${meeting_no}.${ext}"
  if [ -s "$out" ]; then
    sz=$(stat -f%z "$out" 2>/dev/null || echo 0)
    if [ "$sz" -gt 10000 ]; then
      printf "  cached  %3s  %s\n" "$meeting_no" "$out"
      continue
    fi
  fi
  printf "  download %3s  -> %s\n" "$meeting_no" "$out"
  curl -skL --connect-timeout 15 -o "$out" "$url" 2>/dev/null
  sz=$(stat -f%z "$out" 2>/dev/null || echo 0)
  if [ "$sz" -lt 5000 ]; then
    printf "      WARN: only %d bytes\n" "$sz"
    rm -f "$out"
  else
    printf "      OK: %d bytes\n" "$sz"
  fi
done
echo "Done."
