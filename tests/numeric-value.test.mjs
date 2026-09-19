import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { transformSync } from 'esbuild';
import { parseNumeric, numericParserScript } from '../src/lib/numeric-value.mjs';

const fixture = JSON.parse(readFileSync(new URL('./fixtures/numeric-values.json', import.meta.url)));

test('whole numeric cells preserve zeros and valid Indian/Western grouping', () => {
  for (const { value, expected } of fixture) {
    const actual = parseNumeric(value);
    if (expected === null) assert.ok(Number.isNaN(actual), JSON.stringify(value));
    else assert.ok(actual === expected, JSON.stringify(value));
  }
  for (const value of [Infinity, -Infinity, NaN, '9'.repeat(400)]) {
    assert.ok(Number.isNaN(parseNumeric(value)));
  }
});

test('the standalone map/scatter parser matches the bundled parser', () => {
  const context = vm.createContext({});
  vm.runInContext(numericParserScript, context);
  for (const { value, expected } of fixture) {
    const actual = context.parseNumeric(value);
    assert.ok(expected === null ? Number.isNaN(actual) : actual === expected);
  }
});

test('every North-East disposition is excluded from numeric calculations', () => {
  const ledger = JSON.parse(readFileSync(new URL('../public/data-contracts/north-east-value-dispositions.json', import.meta.url)));
  assert.equal(ledger.records.length, 380);
  for (const row of ledger.records) {
    assert.ok(Number.isNaN(parseNumeric(row.sourceValue)), row.observationId);
  }
});

test('map fallback rejects malformed and blank cells while retaining zero', () => {
  const page = readFileSync(new URL('../src/pages/index.astro', import.meta.url), 'utf8');
  const start = page.indexOf('    var DATE_SUFFIX_RE =');
  const end = page.indexOf('    function getVal(', start);
  assert.ok(start >= 0 && end > start);
  const context = vm.createContext({});
  vm.runInContext(numericParserScript + page.slice(start, end), context);
  const pick = context.tryFieldWithPrefix;
  assert.equal(pick({ test__value: '6 5.84' }, 'test__value'), null);
  assert.equal(pick({ test__value: '  ' }, 'test__value'), null);
  assert.equal(pick({ test__value: false }, 'test__value'), null);
  assert.equal(pick({ test__value: 0 }, 'test__value'), 0);
  assert.equal(pick({ test__value: '1,23,456' }, 'test__value'), 123456);
  assert.equal(pick({ test__value_mar_24: '6 5.84' }, 'test__value'), null);
});

test('actual scatter and ranking calculations keep zero and exclude split cells', () => {
  const data = {
    quarters: { current: { tables: { test: { districts: {
      Zero: { x: 0, y: '10' },
      Split: { x: '6 5.84', y: '10' },
      Missing: { x: ' ', y: '10' },
      Normal: { x: '1,234', y: '20' },
    } } } } },
  };
  const context = vm.createContext({
    parseNumeric, masterData: data, selectedQuarter: 'current', selectedCategory: 'test',
    selectedFieldX: 'x', selectedFieldY: 'y', selectedField: 'x', quarterLabel: x => x,
  });
  const explorer = readFileSync(new URL('../src/components/analysis/DataExplorer.svelte', import.meta.url), 'utf8');
  const start = explorer.indexOf('  function getSLBCChartData()');
  const end = explorer.indexOf('  function getCustomChartData()', start);
  vm.runInContext(transformSync(explorer.slice(start, end), { loader: 'ts' }).code, context);
  assert.equal(JSON.stringify(context.getSLBCChartData().x), '[0,1234]');

  const ranking = readFileSync(new URL('../src/components/analysis/DistrictRankings.svelte', import.meta.url), 'utf8');
  const rankingStart = ranking.indexOf('let rankingRows: RankRow[] = $derived.by(() => {');
  const rankingEnd = ranking.indexOf('\n  // Sort rows', rankingStart);
  assert.ok(rankingStart >= 0 && rankingEnd > rankingStart);
  context.$derived = { by: fn => fn() };
  const code = ranking.slice(rankingStart, rankingEnd) + '\nglobalThis.rows = rankingRows;';
  vm.runInContext(transformSync(code, { loader: 'ts' }).code, context);
  assert.equal(JSON.stringify(context.rows.map(r => [r.district, r.value])), '[["Zero",0],["Normal",1234]]');
});
