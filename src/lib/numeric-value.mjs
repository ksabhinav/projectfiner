/**
 * Parse a whole, finite numeric cell. Missing or ambiguous cells return NaN.
 * Keep this function self-contained: the legacy map/scatter scripts embed it.
 * Units, percentage suffixes and source missing markers require separate review.
 */
export function parseNumeric(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : NaN;
  if (typeof value !== 'string') return NaN;
  const text = value.trim();
  const numeric = /^[+-]?(?:(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,2}(?:,[0-9]{2})+,[0-9]{3})(?:\.[0-9]*)?|\.[0-9]+)$/;
  if (!numeric.test(text)) return NaN;
  const number = Number(text.replace(/,/g, ''));
  return Number.isFinite(number) ? number : NaN;
}

// This contains only repository code, never source data or user input.
export const numericParserScript = `var parseNumeric = ${parseNumeric.toString()};`;
