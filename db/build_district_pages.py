#!/usr/bin/env python3
"""
Build per-district aggregation files for /district/<state>/<district>/ landing pages.

Reads every `public/indicators/<indicator>/<quarter>.json`, resolves each row to
the state-scoped LGD geography registry, picks the headline metric per indicator
with fallback chain, and writes:
  - public/districts/index.json                          (list of all pages)
  - public/districts/<state-slug>/<district-slug>.json   (one per district)
  - public/districts/rejects.json                        (unresolved inputs)

The index contains one canonical dataset page per LGD code. Previously published
alias routes are retained as redirect entries but are excluded from the sitemap.

Stays in sync with the headline metrics defined in src/pages/index.astro
(INDICATORS config). To extend: add an entry to HEADLINES below.
"""
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / 'public'
IND_DIR = PUB / 'indicators'
OUT_DIR = PUB / 'districts'
LGD_FILE = PUB / 'district_lgd_codes.json'
PAGE_ALIASES_FILE = ROOT / 'db' / 'district_page_aliases.json'

# Headline metric per indicator. Mirrors INDICATORS[<key>].metrics[0]
# in src/pages/index.astro so a district's "snapshot" lines up with the
# choropleth's default metric. Fallbacks chain catches state-specific
# field-name variants.
HEADLINES = {
    'credit_deposit_ratio': {
        'label': 'Credit-Deposit Ratio',
        'field': 'overall_cd_ratio',
        'unit': '%',
        'fallbacks': ['cd_ratio', 'current_c_d_ratio', 'cdr', 'overall', 'cd_ratio_incl_pou'],
    },
    'pmjdy': {
        'label': 'PMJDY Accounts',
        'field': 'total_pmjdy_no',
        'unit': '',
        'fallbacks': ['total_no_pmjdy', 'pmjdy_no', 'total_no', 'no_of_pmjdy_accounts', 'pmjdy', 'total', 'number_of_pmjdy_accounts_rural', 'total_pmjdy_a_c', 'total_no_pmjdy_a_c', 'total_a_c', 'sum_of_total_a_c', 'pmjdy_total_accounts'],
    },
    'branch_network': {
        'label': 'Bank Branches',
        'field': 'total_branch',
        'unit': '',
        'fallbacks': ['total', 'no_of_branches', 'total_no_of_br', 'total_branche_s', 'total_branches', 'total_branch_es', 'branches_total'],
    },
    'kcc': {
        'label': 'KCC Cards Issued',
        'field': 'total_no_of_kcc',
        'unit': '',
        'fallbacks': ['no_of_kcc', 'kcc_no', 'total_kcc_no', 'total_no'],
    },
    'shg': {
        'label': 'SHGs Savings-Linked',
        'field': 'savings_linked_no',
        'unit': '',
        'fallbacks': ['savings_linked', 'credit_linked_no', 'credit_linked', 'current_fy_savings_linked_no', 'no_of_shgs'],
    },
    'digital_transactions': {
        'label': 'UPI Txns (PhonePe)',
        'field': 'transaction_count',
        'unit': '',
        'fallbacks': [],
    },
    'aadhaar_authentication': {
        'label': 'Aadhaar-Seeded CASA',
        'field': 'no_of_aadhaar_seeded_casa',
        'unit': '',
        'fallbacks': ['aadhaar_seeded_casa', 'number_of_aadhaar_seeded_casa', 'no_of_aadhaar_seeded', 'aadhaar_seeded'],
    },
    'social_security': {
        'label': 'Social Security Enrolment',
        'field': 'total_enrolment_no',
        'unit': '',
        'fallbacks': ['enrolment_under_pmsby', 'enrolment_under_pmjjby', 'enrolment_under_apy'],
    },
    'pmegp': {
        'label': 'PMEGP Disbursed (CY)',
        'field': 'cy_disbursed_no',
        'unit': '',
        'fallbacks': ['disbursed', 'cy_disbursed_a_c_no', 'disbursement_no'],
    },
    'housing_pmay': {
        'label': 'PMAY Loans O/S',
        'field': 'pmay_o_s_no',
        'unit': '',
        'fallbacks': ['rural_housing_loan_o_s_no', 'rural_number', 'rural_no'],
    },
    'sui': {
        'label': 'PMSVANidhi Disbursed',
        'field': 'sanctioned_no',
        'unit': '',
        'fallbacks': ['disbursed_no', 'sui_no'],
    },
    'sc_st_finance': {
        'label': 'SC/ST Advances',
        'field': 'sc_st_advance_amt',
        'unit': '₹',
        'fallbacks': ['advances_to_sc_st_amt', 'advances_amt'],
    },
    'women_finance': {
        'label': 'Women Advances',
        'field': 'women_advance_amt',
        'unit': '₹',
        'fallbacks': ['advances_to_women_amt', 'women_amt'],
    },
    'education_loan': {
        'label': 'Education Loans O/S',
        'field': 'education_loan_o_s_amt',
        'unit': '₹',
        'fallbacks': ['edu_loan_amt', 'education_amt'],
    },
    'priority_sector': {
        'label': 'Priority Sector Achievement',
        'field': 'total_ps_achievement_amt',
        'unit': '₹',
        'fallbacks': ['total_ps', 'priority_sector', 'total_priority'],
    },
    'pmmy_mudra_disbursement': {
        'label': 'MUDRA Disbursement',
        'field': 'total_disbursed_amt',
        'unit': '₹',
        'fallbacks': ['disbursed_amt', 'mudra_amt'],
    },
    'rbi_banking_outlets': {
        'label': 'RBI Banking Outlets',
        'field': 'total_outlets',
        'unit': '',
        'fallbacks': ['outlets', 'total'],
    },
    'nfhs_health_insurance': {
        'label': 'NFHS Health Insurance %',
        'field': 'health_insurance_pct',
        'unit': '%',
        'fallbacks': ['insurance_pct', 'value'],
    },
    'aadhaar_enrollment': {
        'label': 'Aadhaar Enrolment',
        'field': 'total_enrolment',
        'unit': '',
        'fallbacks': ['enrolment', 'aadhaar_count'],
    },
    'nrlm_shg': {
        'label': 'NRLM SHGs',
        'field': 'total_shgs',
        'unit': '',
        'fallbacks': ['shgs', 'shg_count'],
    },
    'capital_markets_access': {
        'label': 'Demat/MF Accounts',
        'field': 'cap_total',
        'unit': '',
        'fallbacks': ['cap_cdsl', 'cap_nsdl'],
    },
    'viirs_nightlights': {
        'label': 'Nightlight Intensity',
        'field': 'nl_mean',
        'unit': '',
        'fallbacks': ['value', 'nightlight'],
    },
    'facebook_rwi': {
        'label': 'Relative Wealth Index',
        'field': 'rwi',
        'unit': '',
        'fallbacks': ['value'],
    },
    'crop_production': {
        'label': 'Total Crop Production',
        'field': 'total_production',
        'unit': '',
        'fallbacks': ['production', 'crop_total'],
    },
    'pmgsy_roads': {
        'label': 'PMGSY Road Length',
        'field': 'length_km',
        'unit': 'km',
        'fallbacks': ['length', 'roads_km'],
    },
    'elevation_terrain': {
        'label': 'Mean Elevation',
        'field': 'elev_mean',
        'unit': 'm',
        'fallbacks': ['elevation', 'mean'],
    },
}

# Indicator display order on the district page — most useful first.
INDICATOR_ORDER = [
    'credit_deposit_ratio',
    'pmjdy',
    'branch_network',
    'kcc',
    'shg',
    'priority_sector',
    'digital_transactions',
    'aadhaar_authentication',
    'social_security',
    'pmegp',
    'pmmy_mudra_disbursement',
    'housing_pmay',
    'sui',
    'sc_st_finance',
    'women_finance',
    'education_loan',
    'rbi_banking_outlets',
    'nfhs_health_insurance',
    'aadhaar_enrollment',
    'nrlm_shg',
    'capital_markets_access',
    'viirs_nightlights',
    'facebook_rwi',
    'crop_production',
    'pmgsy_roads',
    'elevation_terrain',
]

STATE_LABELS = {
    'andaman-nicobar': 'Andaman & Nicobar Islands',
    'chandigarh': 'Chandigarh',
    'dadra-nagar-haveli': 'Dadra & Nagar Haveli',
    'daman-diu': 'Daman & Diu',
    'lakshadweep': 'Lakshadweep',
    'puducherry': 'Puducherry',
    'andhra-pradesh': 'Andhra Pradesh',
    'arunachal-pradesh': 'Arunachal Pradesh',
    'assam': 'Assam',
    'bihar': 'Bihar',
    'chhattisgarh': 'Chhattisgarh',
    'delhi': 'NCT of Delhi',
    'goa': 'Goa',
    'gujarat': 'Gujarat',
    'haryana': 'Haryana',
    'himachal-pradesh': 'Himachal Pradesh',
    'jammu-kashmir': 'Jammu & Kashmir',
    'jharkhand': 'Jharkhand',
    'karnataka': 'Karnataka',
    'kerala': 'Kerala',
    'ladakh': 'Ladakh',
    'madhya-pradesh': 'Madhya Pradesh',
    'maharashtra': 'Maharashtra',
    'manipur': 'Manipur',
    'meghalaya': 'Meghalaya',
    'mizoram': 'Mizoram',
    'nagaland': 'Nagaland',
    'odisha': 'Odisha',
    'punjab': 'Punjab',
    'rajasthan': 'Rajasthan',
    'sikkim': 'Sikkim',
    'tamil-nadu': 'Tamil Nadu',
    'telangana': 'Telangana',
    'tripura': 'Tripura',
    'uttar-pradesh': 'Uttar Pradesh',
    'uttarakhand': 'Uttarakhand',
    'west-bengal': 'West Bengal',
}


def slugify(name: str) -> str:
    """Lowercase, ASCII, hyphen-separated. Mirrors typical SEO slug rules."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s


# Aliases for state values seen in different casings / spellings across indicators.
# SLBC files ship the slug ('punjab'); RBI/NFHS/elevation/FB-RWI etc. ship the human
# name in varying casing ('Punjab', 'JAMMU AND KASHMIR', 'Jammu and Kashmir').
# Normalise everything to the canonical slug.
STATE_NAME_TO_SLUG = {
    'andhra pradesh': 'andhra-pradesh',
    'arunachal pradesh': 'arunachal-pradesh',
    'assam': 'assam',
    'bihar': 'bihar',
    'chhattisgarh': 'chhattisgarh',
    'delhi': 'delhi',
    'nct of delhi': 'delhi',
    'goa': 'goa',
    'gujarat': 'gujarat',
    'haryana': 'haryana',
    'himachal pradesh': 'himachal-pradesh',
    'jammu and kashmir': 'jammu-kashmir',
    'jammu & kashmir': 'jammu-kashmir',
    'jharkhand': 'jharkhand',
    'karnataka': 'karnataka',
    'kerala': 'kerala',
    'ladakh': 'ladakh',
    'madhya pradesh': 'madhya-pradesh',
    'maharashtra': 'maharashtra',
    'manipur': 'manipur',
    'meghalaya': 'meghalaya',
    'mizoram': 'mizoram',
    'nagaland': 'nagaland',
    'odisha': 'odisha',
    'punjab': 'punjab',
    'rajasthan': 'rajasthan',
    'sikkim': 'sikkim',
    'tamil nadu': 'tamil-nadu',
    'telangana': 'telangana',
    'tripura': 'tripura',
    'uttar pradesh': 'uttar-pradesh',
    'uttarakhand': 'uttarakhand',
    'west bengal': 'west-bengal',
    'andaman and nicobar islands': 'andaman-nicobar',
    'andaman & nicobar islands': 'andaman-nicobar',
    'andaman-nicobar': 'andaman-nicobar',
    'chandigarh': 'chandigarh',
    'dadra and nagar haveli': 'dadra-nagar-haveli',
    'the dadra and nagar haveli and daman and diu': 'dadra-nagar-haveli',
    'dadra & nagar haveli & daman & diu': 'dadra-nagar-haveli',
    'dadra-nagar-haveli': 'dadra-nagar-haveli',
    'daman and diu': 'daman-diu',
    'lakshadweep': 'lakshadweep',
    'puducherry': 'puducherry',
}


def normalise_state(raw: str) -> str | None:
    """Map any state value to its canonical slug, or None if unknown."""
    if not raw:
        return None
    key = raw.strip().lower().replace('-', ' ').replace('_', ' ')
    key = re.sub(r"\s+", " ", key)
    if key in STATE_NAME_TO_SLUG:
        return STATE_NAME_TO_SLUG[key]
    # Already a slug? lower-case alphanumerics + hyphens
    direct = slugify(raw)
    if direct in STATE_LABELS or direct in {'andaman-nicobar', 'chandigarh', 'dadra-nagar-haveli', 'daman-diu', 'lakshadweep', 'puducherry'}:
        return direct
    return None


def normalise_district(raw: str) -> str:
    """Normalise a district label for exact, state-scoped alias lookup."""
    return re.sub(r'[^A-Z0-9]+', '', str(raw or '').upper())


class GeographyRegistry:
    """Resolve district labels to one canonical LGD identity within a state."""

    def __init__(self, districts: list[dict], reviewed_aliases: list[dict] | None = None):
        self.by_lgd: dict[int, dict] = {}
        self._lookup: defaultdict[tuple[str, str], set[int]] = defaultdict(set)

        for district in districts:
            state_slug = normalise_state(district.get('state'))
            if not state_slug:
                raise ValueError(f"Unknown state in geography registry: {district.get('state')!r}")
            lgd_code = int(district['lgd_code'])
            canonical = {
                'lgdCode': lgd_code,
                'stateLgdCode': int(district['state_lgd_code']),
                'state': state_slug,
                'stateLabel': STATE_LABELS.get(state_slug, district['state']),
                'district': district['district'],
                'districtSlug': slugify(district['district']),
            }
            existing = self.by_lgd.get(lgd_code)
            if existing and existing != canonical:
                raise ValueError(f'Conflicting geography rows for LGD {lgd_code}')
            self.by_lgd[lgd_code] = canonical
            for name in [district['district'], *district.get('aliases', [])]:
                self._register(state_slug, name, lgd_code)

        for alias in reviewed_aliases or []:
            lgd_code = int(alias['district_lgd'])
            canonical = self.by_lgd.get(lgd_code)
            if canonical is None:
                raise ValueError(f'Reviewed alias references unknown LGD {lgd_code}')
            if canonical['state'] != alias['state']:
                raise ValueError(
                    f"Reviewed alias {alias['alias']!r} crosses state boundary: "
                    f"{alias['state']} != {canonical['state']}"
                )
            self._register(alias['state'], alias['alias'], lgd_code)

    @classmethod
    def from_files(cls, lgd_path=LGD_FILE, aliases_path=PAGE_ALIASES_FILE):
        district_payload = json.loads(Path(lgd_path).read_text())
        alias_payload = json.loads(Path(aliases_path).read_text())
        return cls(district_payload['districts'], alias_payload.get('aliases', []))

    def _register(self, state_slug: str, name: str, lgd_code: int):
        key = (state_slug, normalise_district(name))
        if key[1]:
            self._lookup[key].add(lgd_code)

    def resolve(self, state_slug: str, district_name: str):
        """Return (canonical geography, reason); never fall back across states."""
        candidates = self._lookup.get(
            (state_slug, normalise_district(district_name)), set()
        )
        if not candidates:
            return None, 'unmatched_district'
        if len(candidates) > 1:
            return None, 'ambiguous_district'
        return self.by_lgd[next(iter(candidates))], None


def merge_indicator_entries(entries: list[dict]):
    """Collapse alias observations by quarter and reject conflicting values."""
    by_quarter = defaultdict(list)
    for entry in entries:
        by_quarter[entry['quarter']].append(entry)

    merged = []
    conflicts = []
    for quarter in sorted(by_quarter):
        candidates = by_quarter[quarter]
        signatures = {
            (json.dumps(item['value'], ensure_ascii=False, sort_keys=True), item['field'])
            for item in candidates
        }
        if len(signatures) > 1:
            conflicts.append({
                'quarter': quarter,
                'candidates': sorted(
                    candidates,
                    key=lambda item: (item['sourceDistrictSlug'], item['field']),
                ),
            })
            continue
        chosen = min(
            candidates,
            key=lambda item: (item['sourceDistrictSlug'], item['field']),
        )
        merged.append({
            'quarter': chosen['quarter'],
            'value': chosen['value'],
            'field': chosen['field'],
        })
    return merged, conflicts


def pick_value(row: dict, headline: dict):
    """Return (raw_value, field_used) or (None, None)."""
    fld = headline['field']
    if fld in row and row[fld] not in (None, '', 'N/A'):
        return row[fld], fld
    for fb in headline.get('fallbacks', []):
        if fb in row and row[fb] not in (None, '', 'N/A'):
            return row[fb], fb
    return None, None


def main(metadata_only=False):
    manifest = json.loads((IND_DIR / 'manifest.json').read_text())
    quarters = sorted(manifest['quarters'])  # ascending so series is chronological
    indicators = manifest['indicators']
    registry = GeographyRegistry.from_files()

    # LGD code -> indicator -> [(quarter, value, field, source district slug)]
    series_data = defaultdict(lambda: defaultdict(list))
    source_routes = defaultdict(set)
    reject_records = {}

    def record_reject(reason, state_raw, state_slug, district, indicator, quarter):
        key = (reason, str(state_raw or ''), str(district or ''))
        record = reject_records.setdefault(key, {
            'reason': reason,
            'stateRaw': state_raw,
            'state': state_slug,
            'district': district,
            'appearances': 0,
            'indicators': set(),
            'quarters': set(),
        })
        record['appearances'] += 1
        record['indicators'].add(indicator)
        record['quarters'].add(quarter)

    for ind in indicators:
        if ind not in HEADLINES:
            continue
        headline = HEADLINES[ind]
        for q in quarters:
            f = IND_DIR / ind / f'{q}.json'
            if not f.exists():
                continue
            try:
                payload = json.loads(f.read_text())
            except json.JSONDecodeError as exc:
                raise ValueError(f'Invalid indicator JSON: {f}') from exc
            rows = payload.get('districts', [])
            for row in rows:
                state_raw = row.get('state')
                state_slug = normalise_state(state_raw)
                district = row.get('district')
                if not state_slug:
                    record_reject('unknown_state', state_raw, None, district, ind, q)
                    continue
                if not district or not str(district).strip():
                    record_reject('missing_district', state_raw, state_slug, district, ind, q)
                    continue
                geography, reason = registry.resolve(state_slug, district)
                if geography is None:
                    record_reject(reason, state_raw, state_slug, district, ind, q)
                    continue
                source_slug = slugify(str(district))
                lgd_code = geography['lgdCode']
                source_routes[lgd_code].add(source_slug)
                val, fld = pick_value(row, headline)
                if val is None:
                    continue
                series_data[lgd_code][ind].append({
                    'quarter': q,
                    'value': val,
                    'field': fld,
                    'sourceDistrictSlug': source_slug,
                })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index_entries = []
    supplemental_files = 0

    redirects = []
    canonical_routes = set()

    for lgd_code, ind_map in series_data.items():
        geography = registry.by_lgd[lgd_code]
        state_slug = geography['state']
        district = geography['district']
        district_slug = geography['districtSlug']
        canonical_routes.add((state_slug, district_slug))

        # Determine each indicator's latest reading + sort series ascending
        latest_quarter_global = None
        out_indicators = {}
        for ind in INDICATOR_ORDER:
            entries = ind_map.get(ind)
            if not entries:
                continue
            entries_sorted, conflicts = merge_indicator_entries(entries)
            for conflict in conflicts:
                reject_records[('conflicting_alias_values', str(lgd_code), f'{ind}/{conflict["quarter"]}')] = {
                    'reason': 'conflicting_alias_values',
                    'state': state_slug,
                    'district': district,
                    'lgdCode': lgd_code,
                    'indicator': ind,
                    **conflict,
                }
            if not entries_sorted:
                continue
            latest = entries_sorted[-1]
            if latest_quarter_global is None or latest['quarter'] > latest_quarter_global:
                latest_quarter_global = latest['quarter']
            out_indicators[ind] = {
                'label': HEADLINES[ind]['label'],
                'unit': HEADLINES[ind]['unit'],
                'latest': latest,
                'series': entries_sorted,
            }

        if not out_indicators:
            continue

        out = {
            'lgdCode': lgd_code,
            'stateLgdCode': geography['stateLgdCode'],
            'state': state_slug,
            'stateLabel': geography['stateLabel'],
            'district': district,
            'districtSlug': district_slug,
            'latestQuarter': latest_quarter_global,
            'indicators': out_indicators,
        }
        source_slugs = sorted(source_routes[lgd_code])
        missing_source_files = [
            source_slug for source_slug in source_slugs
            if not (OUT_DIR / state_slug / f'{source_slug}.json').exists()
        ]
        # A metadata-only migration normally reuses an existing canonical
        # payload. If the only committed payload still uses an alias slug, or if
        # committed payloads lag the indicator inputs, write one canonical
        # aggregate so page links never 404 or silently lose observations.
        write_canonical = (
            not metadata_only
            or source_slugs != [district_slug]
            or bool(missing_source_files)
        )
        if write_canonical:
            out_path = OUT_DIR / state_slug / f'{district_slug}.json'
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
            if metadata_only:
                supplemental_files += 1

        data_files = [district_slug] if write_canonical else source_slugs

        index_entries.append({
            'lgdCode': lgd_code,
            'stateLgdCode': geography['stateLgdCode'],
            'state': state_slug,
            'stateLabel': out['stateLabel'],
            'district': district,
            'districtSlug': district_slug,
            'dataFiles': data_files,
            'latestQuarter': latest_quarter_global,
            'indicatorCount': len(out_indicators),
        })

        for alias_slug in sorted(source_routes[lgd_code]):
            if alias_slug != district_slug:
                redirects.append({
                    'state': state_slug,
                    'districtSlug': alias_slug,
                    'to': f'/district/{state_slug}/{district_slug}/',
                    'lgdCode': lgd_code,
                })

    # Sort the index: state asc, district asc
    index_entries.sort(key=lambda e: (e['state'], e['district'].lower()))
    redirects.sort(key=lambda e: (e['state'], e['districtSlug']))

    redirect_routes = {(e['state'], e['districtSlug']) for e in redirects}
    if canonical_routes & redirect_routes:
        collisions = sorted(canonical_routes & redirect_routes)
        raise ValueError(f'Canonical/redirect route collision: {collisions[:5]}')
    if len(canonical_routes) != len(index_entries):
        raise ValueError('Duplicate canonical district route or LGD identity')

    (OUT_DIR / 'index.json').write_text(
        json.dumps({
            'count': len(index_entries),
            'redirectCount': len(redirects),
            'routeCount': len(index_entries) + len(redirects),
            'districts': index_entries,
            'redirects': redirects,
        }, ensure_ascii=False, separators=(',', ':'))
    )

    serialised_rejects = []
    for record in reject_records.values():
        clean = dict(record)
        if isinstance(clean.get('indicators'), set):
            clean['indicators'] = sorted(clean['indicators'])
        if isinstance(clean.get('quarters'), set):
            clean['quarters'] = sorted(clean['quarters'])
        serialised_rejects.append(clean)
    serialised_rejects.sort(key=lambda r: (
        r['reason'], str(r.get('state') or r.get('stateRaw') or ''),
        str(r.get('district') or ''), str(r.get('indicator') or ''),
    ))
    (OUT_DIR / 'rejects.json').write_text(json.dumps({
        'count': len(serialised_rejects),
        'records': serialised_rejects,
    }, ensure_ascii=False, separators=(',', ':')))

    # State-level freshness summary: latest quarter seen per state.
    state_freshness = defaultdict(lambda: '0000-00')
    for e in index_entries:
        if e['latestQuarter'] > state_freshness[e['state']]:
            state_freshness[e['state']] = e['latestQuarter']
    (OUT_DIR / 'state-freshness.json').write_text(
        json.dumps(dict(state_freshness), separators=(',', ':'))
    )

    action = 'indexed' if metadata_only else 'wrote'
    print(
        f'{action} {len(index_entries)} canonical districts; '
        f'{len(redirects)} alias redirects; {len(serialised_rejects)} rejects; '
        f'{supplemental_files} supplemental payloads'
    )
    by_state = defaultdict(int)
    for e in index_entries:
        by_state[e['state']] += 1
    for s in sorted(by_state):
        print(f'  {s:25} {by_state[s]:3} districts  (latest {state_freshness[s]})')

    # Maintain a <!-- begin district urls --> ... <!-- end district urls -->
    # block in public/sitemap.xml so /district/<state>/<district>/ pages
    # are discoverable to search engines. Rewritten in place each run.
    sitemap_path = PUB / 'sitemap.xml'
    sitemap_text = sitemap_path.read_text()
    BEGIN = '<!-- begin district urls -->'
    END = '<!-- end district urls -->'

    url_lines = []
    for e in index_entries:
        url_lines.append(
            f'  <url><loc>https://projectfiner.com/district/{e["state"]}/{e["districtSlug"]}/</loc>'
            f'<changefreq>monthly</changefreq><priority>0.6</priority></url>'
        )
    block = BEGIN + '\n' + '\n'.join(url_lines) + '\n  ' + END

    if BEGIN in sitemap_text and END in sitemap_text:
        # Replace existing block
        start = sitemap_text.index(BEGIN)
        end = sitemap_text.index(END) + len(END)
        sitemap_text = sitemap_text[:start] + block + sitemap_text[end:]
    else:
        # Insert before </urlset>
        sitemap_text = sitemap_text.replace('</urlset>', f'  {block}\n</urlset>')

    sitemap_path.write_text(sitemap_text)
    print(f'updated sitemap.xml with {len(url_lines)} district URLs')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--metadata-only', action='store_true',
        help='Regenerate index, redirects, rejects and sitemap without rewriting district JSON files.',
    )
    args = parser.parse_args()
    main(metadata_only=args.metadata_only)
