#!/bin/bash
# Uttarakhand agenda PDFs — meetings 63rd to 88th
urls=(
"http://www.slbcuttarakhand.com/documents/Agenda88.pdf|88th"
"http://www.slbcuttarakhand.com/documents/Agenda87.pdf|87th"
"http://www.slbcuttarakhand.com/documents/86th  SLBC Agenda.pdf|86th"
"http://www.slbcuttarakhand.com/documents/85th  SLBC Agenda.pdf|85th"
"http://www.slbcuttarakhand.com/documents/84th_Spl_SLBC_AGENDA.pdf|84th_spl"
"http://www.slbcuttarakhand.com/documents/83rd SLBC Agenda.pdf|83rd"
"http://www.slbcuttarakhand.com/documents/82 SLBC AGENDA JUNE 2022- 25.08.2022.pdf|82nd"
"http://www.slbcuttarakhand.com/documents/81stSLBCMeetingAgenda.pdf|81st"
"http://www.slbcuttarakhand.com/documents/SLBC Agenda 040122.pdf|80th"
"http://www.slbcuttarakhand.com/documents/79 SLBC BOOK.pdf|79th"
"http://www.slbcuttarakhand.com/documents/78th Spl. SLBC Agenda RBI.pdf|78th_spl"
"http://www.slbcuttarakhand.com/documents/77TH SLBC MEETING AGENDA.pdf|77th"
"http://www.slbcuttarakhand.com/documents/AGENDA 76TH SLBC MEETING.pdf|76th"
"http://www.slbcuttarakhand.com/documents/Agenda__Special_SLBC_Meeting_date_11.01.2021.pdf|75th_spl"
"http://www.slbcuttarakhand.com/documents/Agenda Special SLBC meeting  dt 051020.pdf|74th_spl"
"http://www.slbcuttarakhand.com/documents/Agenda_71stSLBC.pdf|71st"
"http://www.slbcuttarakhand.com/documents/Agenda_70th_SLBC.pdf|70th"
"http://www.slbcuttarakhand.com/documents/Agenda_69th_SLBC.pdf|69th"
"http://www.slbcuttarakhand.com/documents/Agenda_68th_SLBC_Meeting.pdf|68th"
"http://www.slbcuttarakhand.com/documents/AGENDA 67 th SLBC MEETING.pdf|67th"
"http://www.slbcuttarakhand.com/documents/Agenda  66th SLBC Meeting.pdf|66th"
"http://www.slbcuttarakhand.com/documents/Agenda  65th SLBC meeting date 05.06.2018.pdf|65th"
"http://www.slbcuttarakhand.com/documents/Agenda__64th_SLBC_meeting.pdf|64th"
"http://www.slbcuttarakhand.com/documents/Agenda63rdSLBCmeeting.pdf|63rd"
"http://www.slbcuttarakhand.com/documents/Agenda_62nd_SLBC_meeting.pdf|62nd"
"http://www.slbcuttarakhand.com/documents/Agenda61thSLBCmeeting.pdf|61st"
)
for entry in "${urls[@]}"; do
  IFS='|' read -r url name <<< "$entry"
  echo "Downloading ${name}..."
  curl -skL -o "${name}_agenda.pdf" "$url" 2>/dev/null
  sz=$(stat -f%z "${name}_agenda.pdf" 2>/dev/null || echo 0)
  if [ "$sz" -lt 1000 ]; then
    echo "  WARN: ${name}_agenda.pdf is only ${sz} bytes"
  else
    echo "  OK: ${name}_agenda.pdf ($(echo "scale=1; $sz/1048576" | bc)MB)"
  fi
done
echo "Done downloading Uttarakhand PDFs"
