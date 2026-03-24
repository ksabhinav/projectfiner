#!/usr/bin/env python3
"""Shared district name → LGD code resolver.

Usage:
    from match_districts import DistrictMatcher
    matcher = DistrictMatcher(db_path)
    lgd_code = matcher.resolve("Kamrup Metro", state_lgd=18)  # Returns int or None
"""

import sqlite3
import re
from functools import lru_cache


class DistrictMatcher:
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self._build_caches()
        self.unmatched = []  # [(name, state_info, source)]

    def _build_caches(self):
        """Build lookup caches from districts and aliases tables."""
        # Exact name → lgd_code (by state)
        self._by_name = {}  # (norm_name, state_lgd) → lgd_code
        self._by_name_any = {}  # norm_name → lgd_code (cross-state, for when state unknown)

        for lgd, name, state_lgd in self.db.execute(
            "SELECT lgd_code, name, state_lgd_code FROM districts"
        ):
            key = (self._norm(name), state_lgd)
            self._by_name[key] = lgd
            self._by_name_any[self._norm(name)] = lgd

        # Alias → lgd_code
        self._by_alias = {}  # (norm_alias, state_lgd) → lgd_code
        self._by_alias_any = {}  # norm_alias → lgd_code

        for alias, district_lgd in self.db.execute(
            "SELECT alias, district_lgd FROM district_aliases"
        ):
            state_lgd = self.db.execute(
                "SELECT state_lgd_code FROM districts WHERE lgd_code=?", (district_lgd,)
            ).fetchone()
            if state_lgd:
                self._by_alias[(self._norm(alias), state_lgd[0])] = district_lgd
            self._by_alias_any[self._norm(alias)] = district_lgd

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
        return self._state_slug_to_lgd.get(slug)

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

        if state_slug and not state_lgd:
            state_lgd = self.state_lgd_from_slug(state_slug)

        norm = self._norm(name)
        if not norm:
            return None

        # 1. Exact canonical name (with state)
        if state_lgd:
            result = self._by_name.get((norm, state_lgd))
            if result:
                return result

        # 2. Alias match (with state)
        if state_lgd:
            result = self._by_alias.get((norm, state_lgd))
            if result:
                return result

        # 3. Try stripping common suffixes
        for suffix in ['DISTRICT', 'DIST', 'DT']:
            stripped = norm.rstrip(suffix) if norm.endswith(suffix) else norm
            if stripped != norm:
                if state_lgd:
                    result = self._by_name.get((stripped, state_lgd))
                    if result:
                        return result
                    result = self._by_alias.get((stripped, state_lgd))
                    if result:
                        return result

        # 4. Cross-state fallback (no state constraint)
        result = self._by_name_any.get(norm)
        if result:
            return result
        result = self._by_alias_any.get(norm)
        if result:
            return result

        # Unmatched
        self.unmatched.append((name, state_lgd or state_slug, source))
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
                self._by_alias[(norm, state_lgd[0])] = district_lgd
            self._by_alias_any[norm] = district_lgd
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
