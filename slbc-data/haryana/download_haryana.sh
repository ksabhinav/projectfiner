#!/bin/bash
urls=(
"https://slbcharyana.pnb.bank.in/ovugnort/2026/02/Agenda-Annexure-175th-SLBC-Meeting.zip|175th"
"https://slbcharyana.pnb.in/ovugnort/2025/11/Agenda-&-Annexure-174th-SLBC-Meeting.zip|174th"
"https://slbcharyana.pnb.bank.in/ovugnort/2025/08/Agenda-&-Annexure-173rd-SLBC-Meeting.zip|173rd"
"https://slbcharyana.pnb.bank.in/ovugnort/2025/05/Agenda%20&%20Annexure%20172nd%20SLBC%20Meeting.zip|172nd"
"https://slbcharyana.pnb.bank.in/ovugnort/2025/02/Agenda-Annexure-171st-SLBC-Meeting.zip|171st"
"https://slbcharyana.pnb.bank.in/ovugnort/2024/11/Agenda-Annexure-170th-SLBC-Meeting-1.zip|170th"
"https://slbcharyana.pnb.bank.in/ovugnort/2024/12/Agenda-Annexures-169-SLBC.zip|169th"
"https://slbcharyana.pnb.bank.in/ovugnort/2024/05/Agenda-Annexures-168-SLBC.zip|168th"
"https://slbcharyana.pnb.bank.in/ovugnort/2024/02/Agenda-Annexures-167-SLBC.zip|167th"
"https://slbcharyana.pnb.bank.in/ovugnort/2023/11/Agenda-Annexures-166-SLBC.zip|166th"
"https://slbcharyana.pnb.bank.in/ovugnort/2023/08/New-folder.zip|165th"
"https://slbcharyana.pnb.bank.in/ovugnort/2023/05/Annexures.zip|164th"
"https://slbcharyana.pnb.bank.in/ovugnort/2023/02/ANNEXURES-163-SLBC.zip|163rd"
)
for entry in "${urls[@]}"; do
  IFS='|' read -r url name <<< "$entry"
  echo "Downloading ${name}..."
  curl -skL -o "${name}.zip" "$url" 2>/dev/null
  sz=$(stat -f%z "${name}.zip" 2>/dev/null || echo 0)
  if [ "$sz" -lt 1000 ]; then
    echo "  WARN: ${name}.zip is only ${sz} bytes, may have failed"
  else
    echo "  OK: ${name}.zip ($(echo "scale=1; $sz/1048576" | bc)MB)"
  fi
done
echo "Done downloading Haryana ZIPs"
