#!/usr/bin/env python3
"""
Clean SLBC data for Tripura, Assam, Nagaland, and Sikkim.
Fixes district names, removes junk entries, and cleans OCR artifacts in field names.
Overwrites files in place.
"""

import json
import csv
import os
import re
import shutil
from collections import OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Canonical districts ──────────────────────────────────────────────────────

CANONICAL_DISTRICTS = {
    'tripura': [
        'West Tripura', 'South Tripura', 'North Tripura', 'Dhalai',
        'Khowai', 'Sepahijala', 'Gomati', 'Unakoti'
    ],
    'assam': [
        'Baksa', 'Bajali', 'Barpeta', 'Biswanath', 'Bongaigaon', 'Cachar',
        'Charaideo', 'Chirang', 'Darrang', 'Dhemaji', 'Dhubri', 'Dibrugarh',
        'Dima Hasao', 'Goalpara', 'Golaghat', 'Hailakandi', 'Hojai', 'Jorhat',
        'Kamrup Metro', 'Kamrup Rural', 'Karbi Anglong', 'Karimganj',
        'Kokrajhar', 'Lakhimpur', 'Majuli', 'Morigaon', 'Nagaon', 'Nalbari',
        'Sivasagar', 'Sonitpur', 'South Salmara', 'Tamulpur', 'Tinsukia',
        'Udalguri', 'West Karbi Anglong'
    ],
    'nagaland': [
        'Chumoukedima', 'Dimapur', 'Kiphire', 'Kohima', 'Longleng',
        'Mokokchung', 'Mon', 'Niuland', 'Noklak', 'Peren', 'Phek',
        'Shamator', 'Tseminyu', 'Tuensang', 'Wokha', 'Zunheboto'
    ],
    'sikkim': [
        'Mangan', 'Gangtok', 'Pakyong', 'Namchi', 'Gyalshing', 'Soreng'
    ],
}

# Build lookup: lowercase -> canonical name
CANONICAL_LOOKUP = {}
for state, districts in CANONICAL_DISTRICTS.items():
    lookup = {}
    for d in districts:
        lookup[d.lower()] = d
    CANONICAL_LOOKUP[state] = lookup

# ── Assam spelling variants ──────────────────────────────────────────────────

ASSAM_ALIASES = {
    'choraideo': 'Charaideo',
    'darang': 'Darrang',
    'dhemji': 'Dhemaji',
    'dibrrugarh': 'Dibrugarh',
    'sivsagar': 'Sivasagar',
    'kamrup ( r )': 'Kamrup Rural',
    'kamrup (r)': 'Kamrup Rural',
    'kamrup (rural)': 'Kamrup Rural',
    'kamrup rural': 'Kamrup Rural',
    'kamrup m': 'Kamrup Metro',
    'kamrup metro': 'Kamrup Metro',
    'kamrup': 'Kamrup Metro',  # bare "Kamrup" is ambiguous but likely Metro
    'north cachar hills': 'Dima Hasao',
    'karimganj': 'Karimganj',
}

ASSAM_JUNK = {
    '(c)', 'all districts', 'rebhoi', 'sribhumi', 'northgarohills', 'hojai(nagaon)',
    'name of the',
}


def resolve_tripura_district(name):
    """Resolve a Tripura district name, handling RSETI/RUDSETI strings and prefix errors."""
    orig = name.strip()
    # RSETI pattern: last comma-separated part is the district
    if orig.upper().startswith('RSETI') or orig.upper().startswith('RUDSETI'):
        parts = orig.split(',')
        candidate = parts[-1].strip()
        # Check canonical
        c = CANONICAL_LOOKUP['tripura'].get(candidate.lower())
        if c:
            return c
        # Try without trailing period
        c = CANONICAL_LOOKUP['tripura'].get(candidate.rstrip('.').lower())
        if c:
            return c
        return None

    # Strip number prefix: '1Dhalai' -> 'Dhalai'
    stripped = re.sub(r'^\d+', '', orig).strip()

    # Strip 'DISTT.' suffix
    stripped = re.sub(r'\s*DISTT\.?\s*$', '', stripped, flags=re.IGNORECASE).strip()

    c = CANONICAL_LOOKUP['tripura'].get(stripped.lower())
    if c:
        return c
    return None


def resolve_assam_district(name):
    """Resolve an Assam district name."""
    orig = name.strip()
    low = orig.lower().strip()

    if low in ASSAM_JUNK:
        return None

    # Check aliases first
    if low in ASSAM_ALIASES:
        return ASSAM_ALIASES[low]

    # Check canonical
    c = CANONICAL_LOOKUP['assam'].get(low)
    if c:
        return c

    return None


def resolve_nagaland_district(name):
    """Nagaland districts are clean, just verify."""
    c = CANONICAL_LOOKUP['nagaland'].get(name.strip().lower())
    return c


def resolve_sikkim_district(name):
    """Sikkim: remove state total."""
    low = name.strip().lower()
    if 'total' in low or 'state' in low:
        return None
    c = CANONICAL_LOOKUP['sikkim'].get(low)
    return c


RESOLVERS = {
    'tripura': resolve_tripura_district,
    'assam': resolve_assam_district,
    'nagaland': resolve_nagaland_district,
    'sikkim': resolve_sikkim_district,
}


def clean_field_name(field):
    """Fix OCR artifacts in field names.

    Two types of OCR breaks:
    1. Hyphen-space breaks: 'Anci- llary' -> 'Ancillary'
    2. Mid-word spaces: 'Infrastru cture' -> 'Infrastructure'

    We use a conservative approach: only fix patterns where we can be confident
    the space is an OCR artifact, not a legitimate word boundary.
    """
    # Step 0: Explicit fixes for badly mangled fields
    EXPLICIT_FIXES = {
        'Plantation & ho r tic u lt u re A m o u n t': 'Plantation & horticulture Amount',
        'Plantation & ho rtic u lture A m o un t': 'Plantation & horticulture Amount',
        'Educati on NPS Amt': 'Education NPS Amt',
        'Educati on NPS No': 'Education NPS No',
        'Farm Producti on A/C': 'Farm Production A/C',
        'Farm Producti on amt': 'Farm Production amt',
        'MiNo.rity communities Amt.': 'Minority communities Amt.',
        'MiNo.rity communities No.': 'Minority communities No.',
        'Social Infrastr ucture A/C': 'Social Infrastructure A/C',
        'Farm mechanizati on A/C Nos': 'Farm mechanization A/C Nos',
        'Farm mechanizati on Amount': 'Farm mechanization Amount',
        'Fishery Numbe r of rupay card Issued': 'Fishery Number of rupay card Issued',
        'Fishery Outstandin g amount.': 'Fishery Outstanding amount.',
        'Total Branc h': 'Total Branch',
        "Farmer' s Share of Premiu m (Rs.)": "Farmer's Share of Premium (Rs.)",
        'Educ ation NPS Amt': 'Education NPS Amt',
    }
    if field in EXPLICIT_FIXES:
        return EXPLICIT_FIXES[field]

    # Step 1: Fix hyphen-space-lowercase pattern (clear OCR line break)
    # E.g. 'Anci- llary' -> 'Ancillary', 'Dis- bursed' -> 'Disbursed'
    field = re.sub(r'(\w)- ([a-z])', r'\1\2', field)

    # Step 2: Fix mid-word spaces using a curated set of OCR fragment patterns.
    # These are specific suffix fragments that are clearly not standalone words.
    # Pattern: a word fragment (ending in lowercase) + space + suffix fragment
    OCR_SUFFIX_FRAGMENTS = {
        # 1-char suffixes (clearly not words in context)
        'b', 'c', 'd', 'e', 'f', 'g', 'h', 'k', 'l', 'm', 'n',
        'p', 'r', 's', 't', 'v', 'w', 'x', 'y', 'z',
        # 2-char suffixes that are word fragments, not real words
        'al', 'ar', 'ce', 'ct', 'ed', 'el', 'er', 'es', 'ge', 'ic',
        'le', 'lt', 'ly', 'ng', 'nt', 'on', 'or', 'rd', 're', 'ry',
        'se', 'st', 'te', 'th', 'ts', 'ty', 'ue', 'um', 'un',
        'ur', 'us', 'yd',
        # 3-char suffixes
        'ant', 'age', 'ary', 'ate', 'ble', 'cal', 'ced', 'ent', 'ial',
        'ies', 'ing', 'ion', 'ity', 'ive', 'lar', 'led', 'nal', 'ous',
        'ted', 'ter', 'tes', 'tic', 'tle', 'tor', 'ure', 'ons', 'cts',
        'nce', 'unt',
        # 4-char suffixes
        'able', 'ally', 'ance', 'ated', 'ctor', 'ence', 'ical',
        'ient', 'ings', 'ment', 'ness', 'sion', 'sted', 'tion', 'ture',
        'ties', 'tory', 'ised', 'ized', 'ular',
        # 5-char suffixes
        'ation', 'cture', 'ement', 'ility', 'ional', 'ising',
        'istry', 'iture', 'ments', 'tions', 'ously',
    }

    # But we must NOT merge when the "suffix" is actually a common standalone word.
    # Words that happen to look like suffixes but are real words in financial context:
    REAL_WORDS = {
        'a', 'i', 'in', 'on', 'of', 'to', 'at', 'by', 'as', 'or', 'an',
        'no', 'is', 'it', 'if', 'so', 'up', 'we', 'he', 'do', 'be', 'my',
        'us', 'am', 'me', 'oh', 'ok',
        'the', 'and', 'for', 'not', 'per', 'all', 'any', 'are', 'has',
        'its', 'may', 'new', 'old', 'one', 'our', 'own', 'set', 'tax',
        'two', 'use', 'was', 'who', 'yet', 'act', 'add', 'age', 'ago',
        'aid', 'aim', 'air', 'ban', 'bar', 'bid', 'big', 'bit', 'bus',
        'but', 'buy', 'can', 'cap', 'car', 'cut', 'day', 'due', 'end',
        'era', 'etc', 'eye', 'far', 'few', 'fit', 'fly', 'gap', 'gas',
        'got', 'had', 'her', 'him', 'his', 'hit', 'how', 'key', 'law',
        'lay', 'led', 'let', 'low', 'man', 'map', 'met', 'mid', 'mix',
        'net', 'nil', 'nor', 'now', 'off', 'oil', 'out', 'own', 'pay',
        'put', 'ran', 'raw', 'red', 'ref', 'run', 'sat', 'saw', 'say',
        'six', 'sub', 'sum', 'ten', 'top', 'try', 'van', 'via', 'war',
        'way', 'won', 'yes',
        'also', 'area', 'back', 'bank', 'base', 'been', 'best', 'bond',
        'both', 'call', 'came', 'camp', 'card', 'care', 'case', 'cash',
        'city', 'code', 'come', 'copy', 'core', 'cost', 'crop', 'data',
        'date', 'days', 'deal', 'debt', 'does', 'done', 'down', 'draw',
        'drop', 'dual', 'duty', 'each', 'earn', 'ease', 'east', 'edge',
        'else', 'even', 'ever', 'face', 'fact', 'fall', 'farm', 'fast',
        'file', 'fill', 'film', 'find', 'fine', 'fire', 'firm', 'five',
        'flat', 'flow', 'food', 'foot', 'form', 'four', 'free', 'from',
        'fuel', 'full', 'fund', 'gain', 'gave', 'girl', 'give', 'goal',
        'goes', 'gold', 'gone', 'good', 'grew', 'grow', 'half', 'hall',
        'hand', 'hang', 'hard', 'have', 'head', 'hear', 'heat', 'held',
        'help', 'here', 'high', 'hill', 'hold', 'hole', 'home', 'hope',
        'hour', 'huge', 'hung', 'hunt', 'idea', 'into', 'iron', 'item',
        'jobs', 'join', 'just', 'keen', 'keep', 'kept', 'kind', 'king',
        'knew', 'know', 'lack', 'laid', 'lake', 'land', 'last', 'late',
        'lead', 'left', 'lend', 'less', 'life', 'lift', 'like', 'line',
        'link', 'lion', 'list', 'live', 'load', 'loan', 'lock', 'long',
        'look', 'lord', 'lose', 'loss', 'lost', 'lots', 'love', 'luck',
        'made', 'mail', 'main', 'make', 'male', 'many', 'mark', 'mass',
        'mate', 'mean', 'meet', 'mind', 'mine', 'miss', 'mode', 'mood',
        'more', 'most', 'move', 'much', 'must', 'name', 'near', 'neat',
        'neck', 'need', 'next', 'nice', 'nine', 'node', 'none', 'norm',
        'nose', 'note', 'noun', 'odds', 'once', 'only', 'onto', 'open',
        'oral', 'over', 'pace', 'pack', 'page', 'paid', 'pain', 'pair',
        'palm', 'park', 'part', 'pass', 'past', 'path', 'peak', 'pick',
        'pile', 'plan', 'play', 'plot', 'plus', 'poet', 'pole', 'poll',
        'pool', 'poor', 'port', 'pose', 'post', 'pour', 'pure', 'push',
        'puts', 'quit', 'race', 'rank', 'rare', 'rate', 'read', 'real',
        'rely', 'rent', 'rest', 'rice', 'rich', 'ride', 'ring', 'rise',
        'risk', 'road', 'rock', 'rode', 'role', 'roll', 'roof', 'room',
        'root', 'rope', 'rose', 'rule', 'rush', 'safe', 'said', 'sake',
        'sale', 'salt', 'same', 'sand', 'save', 'says', 'seal', 'seat',
        'seed', 'seek', 'seem', 'seen', 'self', 'sell', 'semi', 'send',
        'sent', 'sept', 'ship', 'shop', 'shot', 'show', 'shut', 'sick',
        'side', 'sigh', 'sign', 'silk', 'sink', 'site', 'size', 'skin',
        'slip', 'slot', 'slow', 'snap', 'snow', 'soap', 'soft', 'soil',
        'sold', 'sole', 'some', 'song', 'soon', 'sort', 'soul', 'span',
        'spin', 'spot', 'star', 'stay', 'stem', 'step', 'stop', 'such',
        'suit', 'sure', 'swim', 'tail', 'take', 'tale', 'talk', 'tall',
        'tank', 'tape', 'task', 'team', 'tell', 'tend', 'tent', 'term',
        'test', 'text', 'than', 'that', 'them', 'then', 'they', 'thin',
        'this', 'thus', 'tied', 'till', 'time', 'tiny', 'told', 'toll',
        'tone', 'took', 'tool', 'tops', 'tore', 'torn', 'tour', 'town',
        'trap', 'tree', 'trim', 'trip', 'true', 'tube', 'tune', 'turn',
        'twin', 'type', 'ugly', 'unit', 'upon', 'urge', 'used', 'user',
        'uses', 'vary', 'vast', 'very', 'vice', 'view', 'void', 'vote',
        'wage', 'wait', 'wake', 'walk', 'wall', 'want', 'ward', 'warm',
        'warn', 'wash', 'wave', 'weak', 'wear', 'week', 'well', 'went',
        'were', 'west', 'what', 'when', 'whom', 'wide', 'wife', 'wild',
        'will', 'wind', 'wine', 'wing', 'wire', 'wise', 'wish', 'with',
        'wood', 'word', 'wore', 'work', 'worn', 'wrap', 'yard', 'yeah',
        'year', 'your', 'zero', 'zone',
        'above', 'about', 'after', 'along', 'among', 'below', 'being',
        'build', 'carry', 'cause', 'check', 'child', 'claim', 'class',
        'clear', 'close', 'count', 'could', 'cover', 'daily', 'drive',
        'early', 'eight', 'empty', 'enter', 'equal', 'error', 'every',
        'exact', 'extra', 'field', 'final', 'first', 'fixed', 'floor',
        'force', 'found', 'fresh', 'front', 'given', 'going', 'grade',
        'grand', 'grant', 'great', 'green', 'group', 'grown', 'guard',
        'guess', 'happy', 'heavy', 'hence', 'house', 'human', 'image',
        'index', 'inner', 'issue', 'joint', 'judge', 'known', 'large',
        'later', 'layer', 'learn', 'least', 'leave', 'legal', 'level',
        'light', 'limit', 'local', 'loose', 'lower', 'lunch', 'major',
        'match', 'meant', 'might', 'minor', 'model', 'money', 'month',
        'moral', 'motor', 'mouth', 'moved', 'never', 'night', 'noise',
        'north', 'noted', 'novel', 'occur', 'offer', 'often', 'order',
        'other', 'outer', 'owner', 'paper', 'party', 'patch', 'peace',
        'phone', 'piece', 'place', 'plain', 'plant', 'plate', 'point',
        'pound', 'power', 'press', 'price', 'pride', 'prime', 'print',
        'prior', 'proof', 'prove', 'quite', 'quote', 'radio', 'raise',
        'range', 'rapid', 'ratio', 'reach', 'ready', 'refer', 'rider',
        'right', 'river', 'robin', 'rough', 'round', 'royal', 'rural',
        'scale', 'scene', 'scope', 'score', 'sense', 'serve', 'seven',
        'shall', 'shape', 'share', 'sharp', 'shift', 'shock', 'shoot',
        'short', 'sight', 'since', 'sixth', 'sixty', 'sleep', 'slide',
        'small', 'smart', 'smile', 'smoke', 'solid', 'solve', 'sorry',
        'sound', 'south', 'space', 'spare', 'speak', 'speed', 'spend',
        'split', 'spoke', 'sport', 'staff', 'stage', 'stand', 'start',
        'state', 'steam', 'steel', 'steep', 'stick', 'still', 'stock',
        'stone', 'stood', 'store', 'storm', 'story', 'strip', 'stuck',
        'study', 'stuff', 'style', 'sugar', 'suite', 'super', 'sweet',
        'swing', 'table', 'taste', 'teach', 'teeth', 'thank', 'theme',
        'there', 'thick', 'thing', 'think', 'third', 'those', 'three',
        'throw', 'tight', 'title', 'today', 'token', 'total', 'touch',
        'tough', 'tower', 'track', 'trade', 'train', 'treat', 'trend',
        'trial', 'tribe', 'trick', 'tried', 'truck', 'truly', 'trust',
        'truth', 'twice', 'uncle', 'under', 'union', 'unite', 'unity',
        'until', 'upper', 'upset', 'urban', 'usage', 'usual', 'valid',
        'value', 'video', 'visit', 'vital', 'voice', 'waste', 'watch',
        'water', 'wheel', 'where', 'which', 'while', 'white', 'whole',
        'whose', 'woman', 'women', 'world', 'worry', 'worse', 'worst',
        'worth', 'would', 'write', 'wrong', 'wrote', 'young', 'youth',
        # Financial / banking terms
        'amount', 'number', 'during', 'period', 'cases', 'camps',
        'metro', 'their', 'these', 'cards', 'loans', 'banks',
        'target', 'limit', 'total', 'lakhs', 'crore',
        'settled', 'pending', 'quarter',
    }

    def should_merge(left_word, right_fragment):
        """Decide if 'left_word right_fragment' is an OCR break to fix."""
        rf = right_fragment.lower()
        # If the right fragment is a common real word, don't merge
        if rf in REAL_WORDS:
            return False
        # If it looks like a word suffix, merge
        if rf in OCR_SUFFIX_FRAGMENTS:
            return True
        # Don't merge if uncertain
        return False

    # Apply mid-word space fixes iteratively
    for _ in range(5):
        parts = field.split(' ')
        new_parts = []
        i = 0
        changed = False
        while i < len(parts):
            if i + 1 < len(parts):
                left = parts[i]
                right = parts[i + 1]
                # Only consider if left ends with lowercase and right starts with lowercase
                if (left and right and left[-1].islower() and right[0].islower()
                        and should_merge(left, right)):
                    new_parts.append(left + right)
                    i += 2
                    changed = True
                    continue
            new_parts.append(parts[i])
            i += 1
        field = ' '.join(new_parts)
        if not changed:
            break

    # Clean up any double spaces
    field = re.sub(r'  +', ' ', field).strip()

    return field


def clean_state(state):
    """Clean one state's data."""
    print(f"\n{'='*60}")
    print(f"Cleaning {state.upper()}")
    print(f"{'='*60}")

    state_dir = os.path.join(BASE, state)
    json_path = os.path.join(state_dir, f'{state}_complete.json')

    with open(json_path, 'r') as f:
        data = json.load(f)

    resolver = RESOLVERS[state]
    canonical_set = set(d.lower() for d in CANONICAL_DISTRICTS[state])

    # Track stats
    districts_before = set()
    districts_after = set()
    fields_cleaned = {}
    districts_removed = set()
    districts_merged = {}

    # ── Clean quarters ────────────────────────────────────────────────────
    for qkey, qval in data['quarters'].items():
        tables_to_remove = []
        for tkey, tval in qval['tables'].items():
            if 'districts' not in tval:
                continue

            old_districts = tval['districts']
            new_districts = {}

            for dname, ddata in old_districts.items():
                districts_before.add(dname)
                canonical = resolver(dname)
                if canonical is None:
                    districts_removed.add(dname)
                    continue

                # Clean field names in ddata
                new_ddata = {}
                for fkey, fval in ddata.items():
                    new_fkey = clean_field_name(fkey)
                    if new_fkey != fkey:
                        fields_cleaned[fkey] = new_fkey
                    new_ddata[new_fkey] = fval

                if canonical in new_districts:
                    # Merge: district appeared under multiple names
                    # Keep existing data, add any new fields
                    if dname not in districts_merged:
                        districts_merged[dname] = canonical
                    for k, v in new_ddata.items():
                        if k not in new_districts[canonical]:
                            new_districts[canonical][k] = v
                else:
                    new_districts[canonical] = new_ddata
                    districts_after.add(canonical)

            if not new_districts:
                tables_to_remove.append(tkey)
            else:
                tval['districts'] = new_districts
                tval['num_districts'] = len(new_districts)

                # Also clean field names in the 'fields' list
                if 'fields' in tval:
                    tval['fields'] = [clean_field_name(f) for f in tval['fields']]

        for tkey in tables_to_remove:
            del qval['tables'][tkey]

    # ── Print stats ───────────────────────────────────────────────────────
    print(f"Districts before: {len(districts_before)}")
    print(f"Districts after:  {len(districts_after)}")
    if districts_removed:
        print(f"Removed ({len(districts_removed)}):")
        for d in sorted(districts_removed):
            print(f"  - {d}")
    if districts_merged:
        print(f"Merged ({len(districts_merged)}):")
        for src, dst in sorted(districts_merged.items()):
            print(f"  - {src} -> {dst}")
    if fields_cleaned:
        print(f"Field names cleaned: {len(fields_cleaned)}")
        for old, new in sorted(fields_cleaned.items()):
            if old != new:
                print(f"  - {old!r} -> {new!r}")

    # ── Write cleaned JSON ────────────────────────────────────────────────
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {json_path}")

    # ── Regenerate quarterly CSVs ─────────────────────────────────────────
    quarterly_dir = os.path.join(state_dir, 'quarterly')
    if os.path.exists(quarterly_dir):
        shutil.rmtree(quarterly_dir)
    os.makedirs(quarterly_dir, exist_ok=True)

    for qkey, qval in data['quarters'].items():
        qdir = os.path.join(quarterly_dir, qkey)
        os.makedirs(qdir, exist_ok=True)

        for tkey, tval in qval['tables'].items():
            if 'districts' not in tval or not tval['districts']:
                continue

            csv_path = os.path.join(qdir, f'{tkey}.csv')
            # Get all field names across districts
            all_fields = []
            for ddata in tval['districts'].values():
                for fk in ddata.keys():
                    if fk not in all_fields:
                        all_fields.append(fk)

            with open(csv_path, 'w', newline='') as cf:
                writer = csv.writer(cf)
                writer.writerow(['district'] + all_fields)
                for dname, ddata in sorted(tval['districts'].items()):
                    row = [dname] + [ddata.get(f, '') for f in all_fields]
                    writer.writerow(row)

    print(f"Regenerated quarterly CSVs in {quarterly_dir}")

    # ── Regenerate timeseries ─────────────────────────────────────────────
    # Build timeseries: each row = one district in one quarter
    all_ts_fields = set()
    ts_rows = []

    for qkey in sorted(data['quarters'].keys()):
        qval = data['quarters'][qkey]
        period = qval.get('period', qkey)
        as_on_date = qval.get('as_on_date', '')
        fy = qval.get('fy', '')

        # Collect all districts and their data across all tables
        district_data = {}
        for tkey, tval in qval['tables'].items():
            if 'districts' not in tval:
                continue
            for dname, ddata in tval['districts'].items():
                if dname not in district_data:
                    district_data[dname] = {}
                for fk, fv in ddata.items():
                    col_name = f'{tkey}__{fk}'.lower().replace(' ', '_').replace('/', '/')
                    # Normalize column name
                    col_name = re.sub(r'[^a-z0-9_/%.(),\'-]', '_', col_name.lower())
                    col_name = re.sub(r'_+', '_', col_name).strip('_')
                    district_data[dname][col_name] = fv
                    all_ts_fields.add(col_name)

        for dname in sorted(district_data.keys()):
            row = {
                'district': dname,
                'period': period,
                'as_on_date': as_on_date,
                'fy': fy,
            }
            row.update(district_data[dname])
            ts_rows.append(row)

    # Sort fields for stable output
    sorted_fields = sorted(all_ts_fields)
    all_columns = ['district', 'period', 'as_on_date', 'fy'] + sorted_fields

    # Write timeseries CSV
    ts_csv_path = os.path.join(state_dir, f'{state}_fi_timeseries.csv')
    with open(ts_csv_path, 'w', newline='') as cf:
        writer = csv.writer(cf)
        writer.writerow(all_columns)
        for row in ts_rows:
            writer.writerow([row.get(c, '') for c in all_columns])
    print(f"Wrote {ts_csv_path}")

    # Write timeseries JSON
    ts_json_path = os.path.join(state_dir, f'{state}_fi_timeseries.json')
    # Group by period
    periods_list = []
    current_period = None
    current_districts = []

    for row in ts_rows:
        if row['period'] != current_period:
            if current_period is not None:
                periods_list.append({
                    'period': current_period,
                    'num_districts': len(current_districts),
                    'districts': current_districts,
                })
            current_period = row['period']
            current_districts = []
        current_districts.append(row)

    if current_period is not None:
        periods_list.append({
            'period': current_period,
            'num_districts': len(current_districts),
            'districts': current_districts,
        })

    ts_json_data = {
        'source': data.get('source', ''),
        'state': data.get('state', state.title()),
        'description': data.get('description', ''),
        'num_periods': len(periods_list),
        'total_records': len(ts_rows),
        'total_fields': len(sorted_fields),
        'periods': periods_list,
    }

    with open(ts_json_path, 'w') as f:
        json.dump(ts_json_data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {ts_json_path}")

    return len(districts_after)


def verify(state):
    """Verify cleaned data."""
    state_dir = os.path.join(BASE, state)
    json_path = os.path.join(state_dir, f'{state}_complete.json')

    with open(json_path, 'r') as f:
        data = json.load(f)

    all_districts = set()
    for qkey, qval in data['quarters'].items():
        for tkey, tval in qval['tables'].items():
            if 'districts' in tval:
                all_districts.update(tval['districts'].keys())

    canonical = set(CANONICAL_DISTRICTS[state])
    extra = all_districts - canonical
    missing = canonical - all_districts

    print(f"\n{state.upper()} verification:")
    print(f"  Unique districts: {len(all_districts)}")
    print(f"  Expected: {len(canonical)}")
    if extra:
        print(f"  EXTRA: {extra}")
    if missing:
        print(f"  Missing (may not appear in all quarters): {missing}")
    if not extra:
        print(f"  OK - no unexpected districts")

    return len(extra) == 0


if __name__ == '__main__':
    results = {}
    for state in ['tripura', 'assam', 'nagaland', 'sikkim']:
        count = clean_state(state)
        results[state] = count

    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}")

    all_ok = True
    for state in ['tripura', 'assam', 'nagaland', 'sikkim']:
        ok = verify(state)
        all_ok = all_ok and ok

    print(f"\nAll states clean: {'YES' if all_ok else 'NO'}")
