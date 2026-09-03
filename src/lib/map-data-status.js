const CSV_COLUMNS = [
  'district',
  'state',
  'indicator',
  'metric',
  'value',
  'requested_period',
  'source_period',
  'status',
  'proxy_from',
  'quality_status',
  'quality_flags',
  'boundary_vintage',
];

function csvCell(value) {
  const text = value == null ? '' : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function buildMapViewCsv(rows) {
  const lines = [CSV_COLUMNS.join(',')];
  for (const row of rows || []) {
    lines.push(CSV_COLUMNS.map((column) => csvCell(row[column])).join(','));
  }
  return `${lines.join('\r\n')}\r\n`;
}

export function mapViewFilename(indicator, requestedPeriod) {
  const safe = (value, fallback) => String(value || fallback)
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '') || fallback;
  return `project-finer-${safe(indicator, 'map')}-${safe(requestedPeriod, 'current')}.csv`;
}

export { CSV_COLUMNS };
