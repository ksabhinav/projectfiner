#!/bin/bash
# Extract all raw/{N}.{zip|rar} into raw/{N}/ subdirs.
# ZIP via `unzip`, RAR via `unar`.
set -u
cd "$(dirname "$0")"
mkdir -p raw

for f in raw/*.zip raw/*.rar; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  name="${base%.*}"
  outdir="raw/${name}"
  if [ -d "$outdir" ] && [ "$(find "$outdir" -name '*.xlsx' 2>/dev/null | head -1)" ]; then
    printf "  cached  %s\n" "$outdir"
    continue
  fi
  mkdir -p "$outdir"
  case "$f" in
    *.zip)
      unzip -qo "$f" -d "$outdir" 2>/dev/null && printf "  ok zip  %s\n" "$outdir" || printf "  FAIL zip %s\n" "$f"
      ;;
    *.rar)
      unar -force-overwrite -quiet -output-directory "$outdir" "$f" >/dev/null 2>&1 && printf "  ok rar  %s\n" "$outdir" || printf "  FAIL rar %s\n" "$f"
      ;;
  esac
done
echo "Done."
