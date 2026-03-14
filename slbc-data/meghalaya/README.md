# SLBC Meghalaya - Financial Inclusion Data

District-level financial inclusion indicators for **Meghalaya**, extracted from quarterly booklet PDFs published by the [State Level Bankers' Committee, North East Region (SLBC NE)](https://slbcne.nic.in/meghalaya/booklet.php).

## Coverage

- **18 quarters**: June 2020 to September 2025
- **12 districts**: East Garo Hills, East Jaintia Hills, East Khasi Hills, Eastern West Khasi Hills, North Garo Hills, Ri Bhoi, South Garo Hills, South West Garo Hills, South West Khasi Hills, West Garo Hills, West Jaintia Hills, West Khasi Hills
- **44 indicator categories** per quarter (for 2022 onwards)
- **606 CSV files** total

## File Structure

```
meghalaya/
  quarterly/                        # Per-quarter CSVs (chronological)
    2020-06/                    # June 2020
      branch_network.csv
      education_loan.csv
      ...
    2020-09/                    # September 2020
    ...
    2025-09/                    # September 2025 (latest)

  meghalaya_fi_timeseries.csv       # All districts x all quarters, wide format
  meghalaya_fi_timeseries.json      # Same data, grouped by quarter
  meghalaya_complete.json           # Master JSON with full extraction metadata
  raw-csv/                          # Raw bankwise CSVs from initial extraction
```

## Quarterly Folders

Each folder under `quarterly/` is named `YYYY-MM` for chronological sorting. Each contains one CSV per indicator category, with rows = districts and columns = fields for that indicator.

| Folder | Quarter | FY | Tables |
|--------|---------|-----|--------|
| `2020-06` | June 2020 | 2020-21 | 22 |
| `2020-09` | September 2020 | 2020-21 | 28 |
| `2020-12` | December 2020 | 2020-21 | 31 |
| `2021-06` | June 2021 | 2021-22 | 2 |
| `2021-09` | September 2021 | 2021-22 | 1 |
| `2021-12` | December 2021 | 2021-22 | 1 |
| `2022-03` | March 2022 | 2021-22 | 42 |
| `2022-06` | June 2022 | 2022-23 | 44 |
| `2022-09` | September 2022 | 2022-23 | 43 |
| `2022-12` | December 2022 | 2022-23 | 43 |
| `2023-03` | March 2023 | 2022-23 | 44 |
| `2023-09` | September 2023 | 2023-24 | 44 |
| `2023-12` | December 2023 | 2023-24 | 44 |
| `2024-06` | June 2024 | 2024-25 | 43 |
| `2024-09` | September 2024 | 2024-25 | 43 |
| `2024-12` | December 2024 | 2024-25 | 44 |
| `2025-06` | June 2025 | 2025-26 | 43 |
| `2025-09` | September 2025 | 2025-26 | 44 |

2021 quarters have fewer tables because only Excel files (from ZIP archives) were available, not full PDF booklets.

## Indicator Categories

Each CSV filename corresponds to an indicator category. All values are district-level.

### Banking Infrastructure
| File | Description |
|------|-------------|
| `branch_network.csv` | Bank branches (rural/semi-urban/urban), ATMs, CSPs (Customer Service Points) |
| `credit_deposit_ratio.csv` | Deposits, advances, and CD ratio by district |

### Annual Credit Plan (ACP)
| File | Description |
|------|-------------|
| `acp_target_achievement.csv` | ACP targets vs achievement |
| `acp_disbursement_agri.csv` | ACP disbursement - Agriculture sector |
| `acp_disbursement_msme.csv` | ACP disbursement - MSME sector |
| `acp_disbursement_other_ps.csv` | ACP disbursement - Other Priority Sector |
| `acp_disbursement_non_ps.csv` | ACP disbursement - Non-Priority Sector |
| `acp_priority_sector_os_npa.csv` | Priority sector outstanding and NPA |
| `acp_npa_outstanding.csv` | ACP NPA outstanding details |

### Sector-wise Outstanding & NPA
| File | Description |
|------|-------------|
| `agri_outstanding.csv` | Agriculture sector outstanding |
| `agri_npa.csv` | Agriculture sector NPA |
| `msme_outstanding.csv` | MSME sector outstanding |
| `msme_npa.csv` | MSME sector NPA |
| `other_ps_outstanding.csv` | Other Priority Sector outstanding |
| `other_ps_npa.csv` | Other Priority Sector NPA |
| `non_ps_outstanding.csv` | Non-Priority Sector outstanding |
| `non_ps_npa.csv` | Non-Priority Sector NPA |
| `weaker_section_os.csv` | Weaker section lending outstanding |
| `govt_sponsored_npa.csv` | Government sponsored schemes NPA |

### Credit Schemes
| File | Description |
|------|-------------|
| `kcc.csv` | Kisan Credit Card |
| `kcc_crop.csv` | KCC crop-wise details |
| `education_loan.csv` | Education loans |
| `housing_pmay.csv` | Housing loans / PMAY |
| `crop_insurance.csv` | Crop insurance (PMFBY - Kharif & Rabi) |

### Government Programmes
| File | Description |
|------|-------------|
| `pmjdy.csv` | Pradhan Mantri Jan Dhan Yojana |
| `pmmy_mudra_disbursement.csv` | PMMY/Mudra loan disbursement (Shishu/Kishore/Tarun) |
| `pmmy_mudra_os_npa.csv` | PMMY/Mudra outstanding and NPA |
| `sui.csv` | Stand Up India scheme |
| `pmegp.csv` | Prime Minister's Employment Generation Programme |
| `social_security.csv` | Social security schemes (PMSBY, PMJJBY, APY) |
| `nrlm.csv` | National Rural Livelihoods Mission |
| `nulm.csv` | National Urban Livelihoods Mission |

### Lending to Special Groups
| File | Description |
|------|-------------|
| `minority_disbursement.csv` | Lending to minorities - disbursement |
| `minority_outstanding.csv` | Lending to minorities - outstanding |
| `sc_st_finance.csv` | Lending to SC/ST |
| `women_finance.csv` | Lending to women |
| `shg.csv` | Self Help Groups |
| `jlg.csv` | Joint Liability Groups |

### Financial Inclusion & Digital
| File | Description |
|------|-------------|
| `fi_village_banking.csv` | Financial inclusion - village banking outlets |
| `fi_kcc.csv` | FI & KCC progress (inactive CSPs, RuPay cards) |
| `digital_transactions.csv` | Digital transactions (UPI, IMPS, BHIM) |
| `aadhaar_authentication.csv` | Aadhaar-enabled transactions |
| `investment_credit_agri_disbursement.csv` | Investment credit (agriculture) - disbursement |
| `investment_credit_agri_outstanding.csv` | Investment credit (agriculture) - outstanding |

### Administrative
| File | Description |
|------|-------------|
| `rseti.csv` | Rural Self Employment Training Institutes |
| `ldm_details.csv` | Lead District Manager details |

## How to Use

### Load a single quarter-indicator

```python
import pandas as pd

df = pd.read_csv("quarterly/2025-09/branch_network.csv")
print(df)
```

### Load all quarters for one indicator

```python
import pandas as pd
from pathlib import Path

frames = []
for folder in sorted(Path("quarterly").iterdir()):
    csv_path = folder / "education_loan.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df["quarter"] = folder.name
        frames.append(df)

combined = pd.concat(frames, ignore_index=True)
```

### Load the full time-series

```python
import pandas as pd

# Wide format: one row per district-quarter, all indicators as columns
ts = pd.read_csv("meghalaya_fi_timeseries.csv")
print(f"{len(ts)} records x {len(ts.columns)} columns")
```

### Load JSON

```python
import json

with open("meghalaya_complete.json") as f:
    data = json.load(f)

for period in data["periods"]:
    print(f"{period['period']}: {period['num_districts']} districts, {len(period['categories'])} categories")
```

## Amounts

All monetary values are in **Rs. Lakhs** (1 Lakh = 100,000 INR) unless otherwise noted in column headers.

## Source

[SLBC NE - Meghalaya Quarterly Booklets](https://slbcne.nic.in/meghalaya/booklet.php)

Data extracted programmatically from PDF booklets using pdfplumber. The PDFs contain landscape-rotated tables with reversed text, requiring character-reversal and transposition during extraction.

## What This Dataset Does NOT Include

The SLBC booklets also contain **bank-wise tables** (same indicators broken down by individual bank rather than by district) and **individual bank scorecards**. These are not included in this dataset. Only district-level aggregates are extracted.

## License

This data is sourced from publicly available government publications. Please cite SLBC NE as the original source when using this data.
