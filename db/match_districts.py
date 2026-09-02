#!/usr/bin/env python3
"""Shared district name → LGD code resolver.

Usage:
    from match_districts import DistrictMatcher
    matcher = DistrictMatcher(db_path)
    lgd_code = matcher.resolve("Kamrup Metro", state_lgd=18)  # Returns int or None
"""

import sqlite3
import re
from collections import defaultdict


class DistrictMatcher:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self._build_caches()
        self.unmatched = []  # [(name, state_info, source)]

    def _build_caches(self):
        """Build lookup caches from districts and aliases tables."""
        # Exact name → lgd_code (by state)
        self._by_name = defaultdict(set)  # (norm_name, state_lgd) → {lgd_code}
        self._by_name_any = defaultdict(set)  # norm_name → {lgd_code}

        for lgd, name, state_lgd in self.db.execute(
            "SELECT lgd_code, name, state_lgd_code FROM districts"
        ):
            key = (self._norm(name), state_lgd)
            self._by_name[key].add(lgd)
            self._by_name_any[self._norm(name)].add(lgd)

        # Alias → lgd_code
        self._by_alias = defaultdict(set)  # (norm_alias, state_lgd) → {lgd_code}
        self._by_alias_any = defaultdict(set)  # norm_alias → {lgd_code}

        for alias, district_lgd in self.db.execute(
            "SELECT alias, district_lgd FROM district_aliases"
        ):
            state_lgd = self.db.execute(
                "SELECT state_lgd_code FROM districts WHERE lgd_code=?", (district_lgd,)
            ).fetchone()
            if state_lgd:
                self._by_alias[(self._norm(alias), state_lgd[0])].add(district_lgd)
            self._by_alias_any[self._norm(alias)].add(district_lgd)

        # State slug → state_lgd
        self._state_slug_to_lgd = {}
        for lgd, slug in self.db.execute("SELECT lgd_code, slug FROM states"):
            self._state_slug_to_lgd[slug] = lgd

    @staticmethod
    def _norm(s):
        """Normalize district name for matching: uppercase, strip non-alphanumeric."""
        if not s:
            return ''
        return re.sub(r'[^A-Z0-9]', '', str(s).upper())

    def state_lgd_from_slug(self, slug):
        """Convert state slug to LGD code."""
        if not slug:
            return None
        return self._state_slug_to_lgd.get(str(slug).strip().lower())

    @staticmethod
    def _unique(codes):
        """Return the only candidate, or None when absent/ambiguous."""
        return next(iter(codes)) if len(codes) == 1 else None

    def _record_unmatched(self, name, state_lgd, state_slug, source):
        self.unmatched.append((name, state_lgd if state_lgd is not None else state_slug, source))

    def resolve(self, name, state_lgd=None, state_slug=None, source=None):
        """Resolve a district name to its LGD code.

        Tries in order:
        1. Exact match on canonical name (within state)
        2. Exact match on alias (within state)
        3. Cross-state exact match (if state unknown)
        4. Normalized match (strip suffixes like 'district')

        Returns lgd_code (int) or None if unmatched.
        """
        if not name or not str(name).strip():
            return None

        state_was_supplied = state_lgd is not None or bool(str(state_slug or '').strip())
        if state_slug and state_lgd is None:
            state_lgd = self.state_lgd_from_slug(state_slug)

        norm = self._norm(name)
        if not norm:
            return None

        candidates = [norm]
        for suffix in ['DISTRICT', 'DIST', 'DT']:
            if norm.endswith(suffix) and len(norm) > len(suffix):
                candidates.append(norm[:-len(suffix)])
                break

        # Prefer state-scoped canonical names and aliases. Treat multiple matches
        # as ambiguous rather than silently selecting whichever row loaded last.
        if state_lgd is not None:
            scoped_matches = set()
            for candidate in candidates:
                scoped_matches.update(self._by_name.get((candidate, state_lgd), set()))
                scoped_matches.update(self._by_alias.get((candidate, state_lgd), set()))
            result = self._unique(scoped_matches)
            if result is not None:
                return result

        # A supplied state is a hard boundary. Never "rescue" a failed match by
        # assigning an identically named district from another state.
        if state_was_supplied:
            self._record_unmatched(name, state_lgd, state_slug, source)
            return None

        # When state is genuinely unknown, resolve only globally unique names.
        cross_state_matches = set()
        for candidate in candidates:
            cross_state_matches.update(self._by_name_any.get(candidate, set()))
            cross_state_matches.update(self._by_alias_any.get(candidate, set()))
        result = self._unique(cross_state_matches)
        if result is not None:
            return result

        # Unmatched
        self._record_unmatched(name, state_lgd, state_slug, source)
        return None

    def add_alias(self, district_lgd, alias, source='import'):
        """Add a new alias to the database and cache."""
        norm = self._norm(alias)
        if not norm:
            return
        try:
            self.db.execute(
                "INSERT OR IGNORE INTO district_aliases (district_lgd, alias, source) VALUES (?, ?, ?)",
                (district_lgd, alias, source)
            )
            self.db.commit()
            # Update cache
            state_lgd = self.db.execute(
                "SELECT state_lgd_code FROM districts WHERE lgd_code=?", (district_lgd,)
            ).fetchone()
            if state_lgd:
                self._by_alias[(norm, state_lgd[0])].add(district_lgd)
            self._by_alias_any[norm].add(district_lgd)
        except Exception:
            pass

    def report_unmatched(self):
        """Print unmatched districts."""
        if not self.unmatched:
            print("  All districts matched!")
            return
        # Deduplicate
        seen = set()
        unique = []
        for name, state, source in self.unmatched:
            key = (self._norm(name), state)
            if key not in seen:
                seen.add(key)
                unique.append((name, state, source))
        print(f"  {len(unique)} unmatched districts:")
        for name, state, source in sorted(unique, key=lambda x: str(x[0]))[:20]:
            print(f"    '{name}' (state={state}, source={source})")
        if len(unique) > 20:
            print(f"    ... and {len(unique) - 20} more")

    def close(self):
        self.db.close()
