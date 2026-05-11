# Project FINER — Data Audit Report

Generated against the regenerated `public/indicators/*.json` files on 2026-05-11.
Run `python3 /tmp/audit_full.txt`-style scripts to refresh.

## 1. Latest-quarter staleness per state

The map's "current quarter" is Dec 2025. How stale is each state relative to that?

| State | Latest CD-ratio quarter | Staleness | Note |
|---|---|---|---|
| Uttarakhand | Mar 2023 | **24 months** | Last 88th SLBC agenda extracted; 89th+ not yet published or scanned-Devanagari |
| Andhra Pradesh | Jun 2024 | **18 months** | `slbcap.nic.in` unreachable; only Wayback-archived PDFs available |
| Karnataka | Jun 2025 | 6 months | 2025-Q3 booklet on slbckarnataka.com not yet ingested |
| Bihar | Sep 2025 | 3 months | 95th agenda is the latest text-native PDF; Dec 2025 may be scanned |
| Jharkhand | Sep 2025 | 3 months | Dec 2025 SLBC pending |
| Odisha | Sep 2025 | 3 months | Dec 2025 SLBC pending |
| 17 other SLBC states | Dec 2025 | **current** | NE portal + WB, MH, RJ, GJ, HR, TS, TN, KE all current |
| Kerala | — | n/a | No CD-ratio extraction yet (uses non-standard PDF tables) |
| Sikkim | — | n/a | Only 3 categories extractable; CD ratio absent |
| Uttar Pradesh | — | n/a | Extractor exists but not yet imported |

**Action recommendations:** flag Uttarakhand + AP on the timeline UI so users see the staleness; UP extraction should be the next high-priority addition.

## 2. Magnitude / unit outliers

### 2a. CD ratio > 200% on tiny deposit bases (likely extraction error)

20 districts post CDR > 200% in Dec 2025 with state-wise deposits < ₹10K lakhs. Tamil Nadu, Telangana and Nagaland dominate. Most likely cause: the SLBC PDF table listed only a subset of bank deposits while reporting the full advances. Likely affected:

| State | District | CDR | Deposits (₹ Lakhs) |
|---|---|---|---|
| TN | Kallakurichi | 323.3% | 5,634 |
| TN | Ariyalur | 288.2% | 4,124 |
| TS | Mahabubabad | 282.3% | 2,613 |
| TS | Jangoan | 280.4% | 2,316 |
| TS | Suryapet | 274.6% | 6,084 |
| TN | Dharmapuri | 260.3% | 9,060 |
| TS | Nagarkurnool | 242.6% | 3,368 |
| TN | Perambalur | 238.7% | 4,565 |
| TN | Villupuram | 235.1% | 9,414 |
| TS | Jogulamba Gadwal | 234.8% | 2,275 |
| ...10 more | | | |

These are real values in the source PDFs but the deposit numbers are evidently miscounted. Until reverified, the choropleth shows these as bright-red high-CDR districts which misleads viewers. **Suggested fix:** flag districts where `cd_ratio > 200 AND total_deposit < 25000 lakhs` in the regenerator as `_suspect: true` and grey them on the map.

### 2b. PMJDY counts > 5 million

Only 2 districts exceed 5M: South 24 Parganas (5.62M) and Murshidabad (5.17M). These are plausible — Bengal districts genuinely have ~10M population with very high BSBD coverage. **No action needed.**

### 2c-d. Internal-consistency checks pass

No district reports zero-balance > total or Aadhaar-seeded > operative. The data passes basic invariants.

### 2e. KCC outstanding ₹/card unrealistically low — West Bengal

All 16 WB districts show outstanding amount per KCC card in the range **₹330–₹2,700**. The typical KCC card carries a sanctioned limit of ₹50,000-₹3,00,000 with utilisation often 70%+. WB's KCC `outstanding_amt` field appears to be reporting **outstanding amount in a different unit** (likely ₹ Crores in source PDF, not converted to Lakhs), or it represents only a fraction (e.g. NPA-only). Worth re-checking the WB extractor and possibly applying a ×100 scale.

### 2f. Quarter-over-quarter swings

No state-level CD ratio shifts more than 40 percentage points between consecutive quarters — extraction is temporally consistent. ✓

## 3. Static-indicator freshness

| Indicator | Data vintage | Refresh-able? | Notes |
|---|---|---|---|
| RBI banking outlets | Downloaded May 2026 | Yes (RBI DBIE API live) | 2.47M outlets · re-download quarterly |
| Capital markets access | Scraped May 2025 (1 year old) | Yes (CDSL/NSDL/AMFI websites) | **Refresh due** — 1 year stale |
| NRLM SHG | Snapshot date unclear | Yes (`nrlm.gov.in` MIS) | 8.6M SHGs · re-download quarterly |
| NFHS-5 | 2019-21 | **No** — NFHS-6 not yet released | 5-year survey cycle; NFHS-6 fieldwork 2024-25, release ~2027 |
| NFHS-4 | 2015-16 | n/a (legacy comparator) | |
| Facebook RWI | 2021 | Wait for next Meta release | One-time research dataset |
| PMGSY roads | Cumulative through 2015 | Yes via SHRUG when refreshed | **10+ years stale** — SHRUG should release updated tables |
| VIIRS nightlights | 2012-2023 (12 annual snapshots) | Yes annually | Refresh due for 2024 |
| Aadhaar enrolment | Apr-Dec 2025 (3 quarterly snapshots) | Yes via UIDAI Hackathon dataset | See 5. below — totals look incomplete |
| PhonePe UPI | Through Mar 2024 | Yes (GitHub repo) | **7 quarters stale** — PhonePe Pulse has not updated; nothing to do until upstream |

**Priority refresh queue:**
1. Capital markets (1 year old, re-scrape CDSL/NSDL/AMFI)
2. RBI banking outlets (quarterly refresh, has been months)
3. NRLM SHG (quarterly snapshot)

## 4. Completely missing states/UTs

Only 2 of 36 Indian states/UTs are absent from the SLBC pipeline:
- **Andaman & Nicobar Islands**
- **Dadra & Nagar Haveli & Daman & Diu**

Both are visible on the choropleth via PhonePe digital_transactions data and the static pan-India indicators (RBI outlets, capital markets, NFHS, SHRUG layers).

States that *are* in the pipeline but with very narrow coverage:
- Sikkim: only digital_transactions; no other SLBC categories
- Kerala: only education_loan with one period; no CD ratio breakdown
- Uttar Pradesh: extractor exists but data not yet ingested
- Andhra Pradesh: 20 quarters CDR-only; no PMJDY/KCC/SHG district breakdown
- Telangana: 13 quarters CDR + branch counts; no PMJDY/KCC/SHG breakdown

States visible on the choropleth via PhonePe + pan-India sources (no SLBC data): Chandigarh, Delhi, Goa, Himachal Pradesh, Jammu & Kashmir, Ladakh, Lakshadweep, Madhya Pradesh, Puducherry, Punjab.

## 5. Aadhaar enrolment partial-data warning

UIDAI quarterly snapshots in `public/indicators/aadhaar_enrollment/`:

| Quarter | Districts | States | Total enrolled |
|---|---|---|---|
| Apr-Jun 2025 | 330 | 28 | **6 lakh** |
| Jul-Sep 2025 | 724 | 36 | 19 lakh |
| Oct-Dec 2025 | 714 | 36 | 23 lakh |

These totals look suspiciously low — UIDAI nationally enrols hundreds of thousands per *day*, so a quarter should run into tens of millions. Either (a) the hackathon dataset is sampled / restricted, or (b) the import script is dropping rows. Worth re-running `db/import_aadhaar.py` against the original CSV and reconciling the row count.

## Summary — what's actionable

| Severity | Item | Effort |
|---|---|---|
| **High** | Re-extract WB KCC outstanding amounts (unit-scale issue) | Medium |
| **High** | Flag 20 TS/TN/NL districts as suspect (CDR with tiny deposit base) | Low (regenerator patch) |
| **Medium** | Re-scrape capital markets DPs (1 year stale) | Medium |
| **Medium** | Refresh RBI banking-outlet snapshot (quarterly) | Low |
| **Medium** | Refresh NRLM SHG snapshot | Low |
| **Medium** | Investigate Aadhaar enrolment totals (off by 100×?) | Medium |
| **Low** | Ingest Uttar Pradesh SLBC (extractor ready) | Medium |
| **Low** | OCR Uttarakhand 61st-75th + AP scanned PDFs to backfill staleness | High |
| **Watching** | PhonePe Pulse upstream — wait for new release | None until upstream |
