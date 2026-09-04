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
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  saveBlob(blob, filename);
}
