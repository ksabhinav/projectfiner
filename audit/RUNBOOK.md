# Off-container runbook — harvest → captions → verification

Everything runnable from artifacts alone is done (header collapse recovered, the
129 CD-ratio failures registered). The remaining work all depends on the **source
PDF corpus**, which this managed container can't fetch — its egress allows only
package registries, so `web.archive.org` and the SLBC hosts return proxy 403.

Run the steps below in **any environment that can reach those hosts and has ~5 GB
of free disk** (a laptop, a VM, a CI runner with network). Nothing here needs the
SQLite DB. Work on the same branch (`claude/odisha-acp-data-flaws-9tv8sn`) so the
manifests and registers update in place.

Prereqs: `python3` (stdlib only) + `pdftotext` (poppler) or `pip install pdfplumber`
for the caption/verification steps. Optional but recommended: an archive.org S3
key/secret (`WAYBACK_ACCESS_KEY`/`WAYBACK_SECRET`) to lift the anon rate limit.

---

## Step 1 — Harvest the corpus (the time-critical, rot-sensitive one)

Order by `audit/source_coverage.csv` posture. **Fragile states first** — they have a
working site but almost no archive, so they rot fastest.

```bash
# 1a. live_only_fragile (15) — snapshot what the live portals serve NOW
for s in delhi haryana himachal-pradesh jammu-kashmir karnataka madhya-pradesh \
         maharashtra punjab rajasthan tamil-nadu telangana tripura \
         uttar-pradesh uttarakhand west-bengal; do
  python3 audit/harvest.py --states "$s" --delay 5
done

# 1b. archive_only (1) — live site gone, pull from Wayback CDX (120 snaps back to 2010)
python3 audit/harvest.py --wayback --states andhra-pradesh --delay 6

# 1c. ok (15) — live + deep archive; harvest live, Wayback is the backstop
python3 audit/harvest.py --states arunachal-pradesh,assam,bihar,chhattisgarh,goa,\
gujarat,jharkhand,kerala,ladakh,manipur,meghalaya,mizoram,nagaland,odisha,sikkim --delay 5
```

PDFs land in `sources/<state>/` (gitignored); provenance (sha256, origin URL,
retrieved-at, status) appends to `audit/source_manifest.csv` (**commit this**).
`harvest.py` is resumable — re-run to continue after an interruption; it skips
what it already has and marks Wayback-truncated captures so it won't refetch them.

**Watch for:** anon SPN/CDX rate limits (~15 req/min — the 5 s delay stays under);
CDX 503s (just re-run); Wayback 1 MB truncation on large PDFs (recorded as
`status=truncated`; recover via an alternate snapshot timestamp or the live file).

**Exit:** `audit/source_manifest.csv` has an `ok`/`truncated` row for ≥95% of the
states above; orphans (none currently) flagged.

---

## Step 2 — Caption unit-tier (resolves the 7 unresolved unit states)

Phase 2 left 4 states `UNKNOWN` (goa, odisha, punjab, sikkim — no deposit anchor)
and 3 `low`-confidence (west-bengal, tamil-nadu, uttar-pradesh — magnitude only).
The caption tier reads the unit straight off the PDF (`(Amount in Rs. Crore)` …):

```bash
python3 audit/unit_resolver.py --sources sources     # caption > magnitude > doctrine
```

Every state whose PDF caption is found flips to `unit_source=caption`,
`confidence=high` in `audit/units.yaml` / `audit/unit_findings.csv`. Confirm the 8
crore-scale conflicts (west-bengal, bihar, karnataka, tamil-nadu, andhra-pradesh,
chhattisgarh, telangana, uttar-pradesh) are caption-confirmed before acting on the
100×-normalisation. **Commit** the refreshed `units.yaml` / `unit_findings.csv`.

---

## Step 3 — Verify + re-extract the 95 quarantined defects

`audit/known_issues.csv` lists the 95 genuine CD-ratio defects (34 others are
definitional — leave them). Priority by count: jharkhand 36, chhattisgarh 25
(mostly the Dec 2022 quarter), uttarakhand 13, up 10, delhi 9, kerala 2.

For each affected `(state, quarter)` — locate its PDF in `sources/<state>/` (via
`source_manifest.csv`), then:

1. **Pull the adjudication sample** (stratified, over-samples the failing cells):
   ```bash
   python3 audit/verify.py --sample jharkhand:credit_deposit_ratio --tier A
   ```
2. **Dual-extract** the table with a second, structurally different parser (a VLM
   is the ideal counter-method to the production geometry parser — see the note
   on vision in the program history) and feed both readings to `verify.diff_tables()`.
   Agreement auto-verifies; disagreement goes to human adjudication against the
   page image.
3. **Re-extract** the misparsed rows from source and patch `complete.json` /
   `_fi_timeseries.*` — gate the same way the header repairs did (a change must be
   justified by the source, never by internal derivation).
4. For `garbage_row` cells (Chhattisgarh Dec 2022: `deposit=16` etc.), the whole
   row is wrong — re-extract the entire table, don't patch cells.
5. For `unit_mismatch` cells (uttarakhand ×13), the source tells you which of
   deposit/advance is ×100 off; apply the single-field correction.

**Exit:** `python3 audit/verify.py && python3 audit/triage.py` shows the defect
count falling from 129 toward the 34 definitional floor; update `known_issues.csv`
dispositions from `quarantine` to `fixed`/`accepted`.

---

## Step 4 — Re-measure and record

```bash
python3 audit/verify.py          # reconciliation + registry recon columns
python3 audit/triage.py          # root-cause rollup
python3 audit/flag_cd_ratio_issues.py   # refresh the register + registry flag
```

Commit the refreshed `audit/*.csv`. The registry is the running scoreboard:
`recon_fail_rate`, `cd_ratio_defects`, `unit_declared`/`unit_source` per table.

---

## What "done" looks like (this slice)

- [ ] `source_manifest.csv` covers ≥95% of states; PDFs hashed
- [ ] `units.yaml`: all 31 states have a unit, ≥27 at `confidence≥medium`, the 8
      crore conflicts caption-confirmed
- [ ] `known_issues.csv`: 95 defects resolved or dispositioned; only the ~34
      definitional remain, marked `accepted`
- [ ] reconciliation back down to the definitional floor

Beyond this slice, the larger program (dual-extraction verification of Tier-A
tables, provenance backfill, the pre-publish gate) is laid out in
`finer_integrity_program.md`.
