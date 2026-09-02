import test from 'node:test';
import assert from 'node:assert/strict';

import { mergeDistrictData } from '../src/lib/district-page-data.js';

const entry = {
  lgdCode: 200,
  stateLgdCode: 10,
  state: 'bihar',
  stateLabel: 'Bihar',
  district: 'Kaimur (bhabua)',
  districtSlug: 'kaimur-bhabua',
};

function payload(district, quarter, value) {
  return {
    state: 'bihar',
    district,
    indicators: {
      credit_deposit_ratio: {
        label: 'Credit-Deposit Ratio',
        unit: '%',
        series: [{ quarter, value, field: 'cd_ratio' }],
      },
    },
  };
}

test('legacy district aliases merge into one LGD-backed page', () => {
  const merged = mergeDistrictData(entry, [
    payload('Kaimur', '2024-03', 40),
    payload('Kaimur (bhabua)', '2024-06', 42),
  ]);

  assert.equal(merged.lgdCode, 200);
  assert.equal(merged.district, 'Kaimur (bhabua)');
  assert.equal(merged.latestQuarter, '2024-06');
  assert.deepEqual(
    merged.indicators.credit_deposit_ratio.series.map(({ quarter }) => quarter),
    ['2024-03', '2024-06'],
  );
});

test('cross-state source payloads fail the build', () => {
  const wrongState = payload('Kaimur', '2024-03', 40);
  wrongState.state = 'uttar-pradesh';
  assert.throws(
    () => mergeDistrictData(entry, [wrongState]),
    /Cross-state district payload/,
  );
});

test('conflicting alias values fail instead of using file order', () => {
  assert.throws(
    () => mergeDistrictData(entry, [
      payload('Kaimur', '2024-03', 40),
      payload('Kaimur (bhabua)', '2024-03', 99),
    ]),
    /Conflicting credit_deposit_ratio value/,
  );
});
