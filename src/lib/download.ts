export function saveBlob(blob: Blob, name: string) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function rowsToCsv(rows: string[][]): string {
  return rows.map(r => r.map(v => {
    const s = String(v).replace(/"/g, '""');
    return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s}"` : s;
  }).join(',')).join('\n');
}

export function downloadCsv(rows: string[][], filename: string) {
  const csv = rowsToCsv(rows);
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  saveBlob(blob, filename);
}

export async function downloadXlsx(
  sheets: { name: string; rows: string[][] }[],
  filename: string
) {
  const XLSX = await import('xlsx');
  const wb = XLSX.utils.book_new();
  for (const sheet of sheets) {
    const ws = XLSX.utils.aoa_to_sheet(sheet.rows);
    ws['!cols'] = sheet.rows[0]?.map(h => ({ wch: Math.max(String(h).length + 2, 14) }));
    XLSX.utils.book_append_sheet(wb, ws, sheet.name.slice(0, 31));
  }
  XLSX.writeFile(wb, filename);
}
