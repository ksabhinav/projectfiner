#!/usr/bin/env python3
"""
Build a per-district 1200×630 PNG for Open Graph social previews.

Reads public/districts/<state>/<district>.json (one per page) and writes
public/og/district/<state>/<district>.png. Each card shows:

  - Brand mark + FINER wordmark (top-left)
  - District name + state (centred headline)
  - Up to 3 headline indicator cards (latest value · label)
  - URL footer (projectfiner.com/district/<state>/<district>)

Uses the same Fraunces/IBM Plex Mono typography + atlas palette as the
site, rendered through cairosvg. Output is identical sizing to the
site-wide og-image.png (1200×630).

Idempotent: skips PNGs that are newer than their source JSON. Pass
--force to regenerate everything.

Run:
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 scripts/build_og_district_images.py
"""
import argparse
import html
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('DYLD_FALLBACK_LIBRARY_PATH', '/opt/homebrew/lib')
os.environ.setdefault('DYLD_LIBRARY_PATH', '/opt/homebrew/lib')

import cairosvg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DISTRICTS_DIR = ROOT / 'public/districts'
OUT_DIR = ROOT / 'public/og/district'

# Indicators to feature on the OG card. First match wins per-district, so
# the card always surfaces the most "interesting" of what's available.
# Priority loosely mirrors the homepage choropleth's default ordering.
FEATURED = [
    'credit_deposit_ratio',
    'pmjdy',
    'priority_sector',
    'branch_network',
    'kcc',
    'shg',
    'social_security',
    'digital_transactions',
    'aadhaar_authentication',
]

# Up to 3 cards on the OG image. After the headline indicator, pick
# the two next-most-prominent that have data.
CARDS_PER_OG = 3


def fmt_value(v, unit: str) -> str:
    """Mirror DistrictPage.svelte's fmtValue so OG cards match the page."""
    if v in (None, ''):
        return '—'
    try:
        n = float(v) if not isinstance(v, (int, float)) else v
    except (TypeError, ValueError):
        return str(v)
    if unit == '%':
        return f'{n:.2f}%'
    if unit == '₹':  # ₹
        if abs(n) >= 100:
            return f'₹{n/100:,.1f} Cr'
        return f'₹{n:,.1f} L'
    if unit in ('km', 'm'):
        return f'{n:,.1f} {unit}'
    # Plain count
    if abs(n) >= 1_00_00_000:  # ≥ 1 Cr
        return f'{n/1_00_00_000:,.1f} Cr'
    if abs(n) >= 1_00_000:  # ≥ 1 L
        return f'{n/1_00_000:,.1f} L'
    if abs(n) >= 1000:
        return f'{int(n):,}'
    if n == int(n):
        return f'{int(n)}'
    return f'{n:,.2f}'


def fmt_quarter(q: str) -> str:
    """'2025-12' → 'Dec 2025'."""
    if not q or len(q) != 7:
        return q
    y, m = q.split('-')
    months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        return f'{months[int(m)]} {y}'
    except (IndexError, ValueError):
        return q


def pick_cards(data: dict) -> list[tuple[str, str, str]]:
    """Return [(label, value_str, quarter)] in display order."""
    inds = data.get('indicators', {})
    out: list[tuple[str, str, str]] = []
    for key in FEATURED:
        if key not in inds or len(out) >= CARDS_PER_OG:
            continue
        ind = inds[key]
        latest = ind.get('latest', {})
        if latest.get('value') in (None, ''):
            continue
        out.append((
            ind['label'],
            fmt_value(latest['value'], ind.get('unit', '')),
            fmt_quarter(latest.get('quarter', '')),
        ))
    # If still under 3 cards (sparse states), fill from whatever indicators exist.
    if len(out) < CARDS_PER_OG:
        for key, ind in inds.items():
            if key in FEATURED or len(out) >= CARDS_PER_OG:
                continue
            latest = ind.get('latest', {})
            if latest.get('value') in (None, ''):
                continue
            out.append((
                ind['label'],
                fmt_value(latest['value'], ind.get('unit', '')),
                fmt_quarter(latest.get('quarter', '')),
            ))
    return out


def build_svg(data: dict) -> str:
    """Render the OG card as an SVG string for cairosvg."""
    district = html.escape(data['district'])
    state = html.escape(data['stateLabel'])
    cards = pick_cards(data)
    url_path = f"projectfiner.com/district/{data['state']}/{data['districtSlug']}"
    latest_label = fmt_quarter(data.get('latestQuarter', ''))

    # Card layout: 3 columns equally spaced inside x=80..1120 = 1040 wide.
    # Card width 320, gap 40, so 320*3 + 40*2 = 1040. Perfect fit.
    card_w = 320
    card_gap = 40
    card_y = 380
    card_h = 150
    base_x = 80
    cards_svg = []
    for i, (label, value, quarter) in enumerate(cards):
        x = base_x + i * (card_w + card_gap)
        label_safe = html.escape(label)
        value_safe = html.escape(value)
        quarter_safe = html.escape(quarter)
        cards_svg.append(f'''
        <g transform="translate({x}, {card_y})">
          <rect width="{card_w}" height="{card_h}" rx="8" fill="#FFFFFF" fill-opacity="0.55" stroke="#E8E2D5" stroke-width="1"/>
          <text x="20" y="32" class="mono" font-size="13" fill="#6E665E" letter-spacing="0.5">{label_safe.upper()}</text>
          <text x="20" y="92" font-size="40" font-weight="400" letter-spacing="-1" fill="#1B140E">{value_safe}</text>
          <text x="20" y="128" class="mono" font-size="12" fill="#6E665E">LATEST · {quarter_safe.upper()}</text>
        </g>''')

    # If fewer than 3 cards, centre what we have rather than leaving holes.
    if len(cards) < 3:
        offset = (3 - len(cards)) * (card_w + card_gap) // 2
        # rewrite x positions
        cards_svg = []
        for i, (label, value, quarter) in enumerate(cards):
            x = base_x + offset + i * (card_w + card_gap)
            label_safe = html.escape(label)
            value_safe = html.escape(value)
            quarter_safe = html.escape(quarter)
            cards_svg.append(f'''
        <g transform="translate({x}, {card_y})">
          <rect width="{card_w}" height="{card_h}" rx="8" fill="#FFFFFF" fill-opacity="0.55" stroke="#E8E2D5" stroke-width="1"/>
          <text x="20" y="32" class="mono" font-size="13" fill="#6E665E" letter-spacing="0.5">{label_safe.upper()}</text>
          <text x="20" y="92" font-size="40" font-weight="400" letter-spacing="-1" fill="#1B140E">{value_safe}</text>
          <text x="20" y="128" class="mono" font-size="12" fill="#6E665E">LATEST · {quarter_safe.upper()}</text>
        </g>''')

    cards_block = ''.join(cards_svg)

    # Headline sizing: district names vary in length. Hard-coded 72px works
    # for most names; clamp to a smaller font for very long ones.
    headline_size = 76 if len(district) <= 14 else (64 if len(district) <= 20 else 54)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <defs>
    <linearGradient id="hairline" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"  stop-color="#B84A2E"/>
      <stop offset="100%" stop-color="#D4A24A"/>
    </linearGradient>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&amp;family=Source+Serif+4:wght@300..600&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap');
      text {{ font-family: 'Fraunces', Georgia, serif; }}
      .mono {{ font-family: 'IBM Plex Mono', monospace; }}
    </style>
  </defs>

  <rect width="1200" height="630" fill="#F4EFE6"/>
  <rect x="0" y="0" width="1200" height="12" fill="url(#hairline)"/>

  <!-- Brand block: four-bar mark + FINER. -->
  <g transform="translate(80, 70)">
    <g transform="scale(3)">
      <rect x="0" y="2"  width="7"  height="3" fill="#B84A2E"/>
      <rect x="0" y="7"  width="11" height="3" fill="#1B140E"/>
      <rect x="0" y="12" width="18" height="3" fill="#1B140E"/>
      <rect x="0" y="17" width="9"  height="3" fill="#D4A24A"/>
    </g>
    <text x="74" y="56" font-size="44" font-weight="400" letter-spacing="-0.8" fill="#1B140E">FINER<tspan fill="#B84A2E">.</tspan></text>
  </g>

  <!-- Top-right meta -->
  <g class="mono" font-size="15" text-anchor="end">
    <text x="1120" y="76" fill="#6E665E">DISTRICT PROFILE</text>
    <text x="1120" y="100" fill="#6E665E">{html.escape(latest_label).upper() if latest_label else 'INDIA'}</text>
  </g>

  <!-- Headline: District -->
  <text x="80" y="240" font-size="{headline_size}" font-weight="400" letter-spacing="-2" fill="#1B140E">{district}</text>
  <text x="80" y="290" font-size="28" font-weight="400" font-style="italic" fill="#3D332A" font-family="'Source Serif 4', Georgia, serif">{state}</text>

  <!-- Indicator cards -->
  {cards_block}

  <!-- Footer URL -->
  <g class="mono" font-size="16">
    <text x="80" y="588" fill="#6E665E">{html.escape(url_path)}</text>
    <text x="1120" y="588" fill="#B84A2E" text-anchor="end">PROJECTFINER.COM</text>
  </g>
</svg>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true',
                        help='Regenerate even if output is newer than input.')
    parser.add_argument('--limit', type=int, default=0,
                        help='Render only the first N districts (for quick tests).')
    args = parser.parse_args()

    index_path = DISTRICTS_DIR / 'index.json'
    if not index_path.exists():
        print(f'ERROR: {index_path} missing. Run db/build_district_pages.py first.')
        sys.exit(1)

    index = json.loads(index_path.read_text())
    rows = index['districts']
    if args.limit:
        rows = rows[: args.limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rendered, skipped = 0, 0
    for row in rows:
        state = row['state']
        slug = row['districtSlug']
        src = DISTRICTS_DIR / state / f'{slug}.json'
        dst = OUT_DIR / state / f'{slug}.png'
        if not src.exists():
            continue
        if dst.exists() and not args.force and dst.stat().st_mtime >= src.stat().st_mtime:
            skipped += 1
            continue
        data = json.loads(src.read_text())
        svg = build_svg(data)
        dst.parent.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(bytestring=svg.encode('utf-8'),
                         write_to=str(dst),
                         output_width=1200, output_height=630)
        rendered += 1
        if rendered % 50 == 0:
            print(f'  …{rendered} rendered')

    print(f'done: {rendered} rendered, {skipped} skipped (already up to date)')
    print(f'output: {OUT_DIR.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
