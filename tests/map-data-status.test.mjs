import assert from 'node:assert/strict';
import test from 'node:test';

import { buildMapViewCsv, mapViewFilename } from '../src/lib/map-data-status.js';

test('map export includes period, proxy, and quality status fields', () => {
  const csv = buildMapViewCsv([{
    district: 'Example, East',
    state: 'Example State',
    indicator: 'credit_deposit_ratio',
    metric: 'Overall CD Ratio (%)',
    value: 42.5,
    requested_period: '2026-03',
    source_period: '2025-12',
    status: 'proxy',
    proxy_from: 'Example Parent',
    quality_status: 'suspect',
    quality_flags: 'source_document_unlinked|boundary_not_harmonised',
    boundary_vintage: 'undocumented',
  }]);

  assert.match(csv, /requested_period,source_period,status,proxy_from,quality_status,quality_flags,boundary_vintage/);
  assert.match(csv, /"Example, East"/);
  assert.match(csv, /2026-03,2025-12,proxy,Example Parent,suspect/);
  assert.match(csv, /boundary_not_harmonised,undocumented/);
});

test('map export filenames are deterministic and safe', () => {
  assert.equal(
    mapViewFilename('Credit / Deposit Ratio', '2026-03'),
    'project-finer-credit-deposit-ratio-2026-03.csv',
  );
});
