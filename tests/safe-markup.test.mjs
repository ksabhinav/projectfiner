import test from 'node:test';
import assert from 'node:assert/strict';

import {
  escapeHtml,
  formatEmphasis,
  formatMarkdown,
  formatSummary,
} from '../src/lib/safe-markup.js';

test('escapeHtml encodes executable markup', () => {
  const output = escapeHtml('<img src=x onerror="alert(1)">');
  assert.equal(output, '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  assert.doesNotMatch(output, /<img/i);
});

test('Ask formatting preserves supported Markdown after escaping input HTML', () => {
  const output = formatMarkdown('**Result:** <script>alert(1)</script>');
  assert.match(output, /<strong>Result:<\/strong>/);
  assert.match(output, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(output, /<script>/i);
});

test('summary formatting supports bold without trusting source HTML', () => {
  const output = formatSummary('**Finding**\n<img src=x>');
  assert.equal(output, '<strong>Finding</strong><br>&lt;img src=x&gt;');
});

test('finding formatting allows only attribute-free emphasis tags', () => {
  assert.equal(formatEmphasis('A <em>curious</em> result'), 'A <em>curious</em> result');
  const output = formatEmphasis('<em onclick="alert(1)">unsafe</em>');
  assert.match(output, /&lt;em onclick=/);
  assert.doesNotMatch(output, /<em onclick=/);
});
