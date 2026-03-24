# Project FINER - Data Validation Report

Generated: 2026-03-24 19:33:38

States processed: 22
Total issues: **70** (Critical: 47, Warning: 21, Info: 2)

## Summary by State and Issue Type

| State | 10x_jump | missing_district | outlier | period_gap | Total |
| --- | --- | --- | --- | --- | --- |
| arunachal-pradesh | - | 4 | - | 1 | 5 |
| assam | - | 4 | - | - | 4 |
| bihar | - | - | - | - | 0 |
| chhattisgarh | - | - | - | - | 0 |
| gujarat | - | - | - | - | 0 |
| haryana | 47 | - | 2 | - | 49 |
| jharkhand | - | - | - | - | 0 |
| karnataka | - | 2 | - | - | 2 |
| kerala | - | 1 | - | 1 | 2 |
| maharashtra | - | - | - | - | 0 |
| manipur | - | - | - | 1 | 1 |
| meghalaya | - | - | - | - | 0 |
| mizoram | - | - | - | 1 | 1 |
| nagaland | - | 1 | - | 1 | 2 |
| odisha | - | - | - | 1 | 1 |
| rajasthan | - | - | - | - | 0 |
| sikkim | - | - | - | 1 | 1 |
| tamil-nadu | - | - | - | - | 0 |
| telangana | - | - | - | - | 0 |
| tripura | - | - | - | 1 | 1 |
| uttarakhand | - | - | - | - | 0 |
| west-bengal | - | - | - | 1 | 1 |

## Detailed Findings


### Arunachal Pradesh


#### Missing District (4 issues)

- [WARNING] **Kamle** | `-` @ December 2020: District missing from this period but present in adjacent periods
- [WARNING] **Capital Complex** | `-` @ December 2022: District missing from this period but present in adjacent periods
- [WARNING] **Capital Complex** | `-` @ December 2023: District missing from this period but present in adjacent periods
- [WARNING] **Capital Complex** | `-` @ March 2024: District missing from this period but present in adjacent periods

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 6 quarter(s): June 2018, September 2018, December 2018, March 2019, June 2019, March 2020

### Assam


#### Missing District (4 issues)

- [WARNING] **Dimahasao** | `-` @ September 2017: District missing from this period but present in adjacent periods
- [WARNING] **Dimahasao** | `-` @ December 2017: District missing from this period but present in adjacent periods
- [WARNING] **Kamrup Rural** | `-` @ September 2019: District missing from this period but present in adjacent periods
- [WARNING] **Kamrup Rural** | `-` @ June 2024: District missing from this period but present in adjacent periods

### Haryana


#### 10X Jump (47 issues)

- [**CRITICAL**] **AMBALA** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 8.17%: 416.00 (Sep 2025) -> 34.00 (Dec 2025)
- [**CRITICAL**] **AMBALA** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 3.26%: 92.00 (Mar 2024) -> 3.00 (Jun 2024)
- [**CRITICAL**] **BHIWANI** | `hsfdc_sponsored` @ Jun 2024: Value dropped to 8.71%: 1,435.00 (Mar 2024) -> 125.00 (Jun 2024)
- [**CRITICAL**] **FARIDABAD** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 7.42%: 391.00 (Sep 2025) -> 29.00 (Dec 2025)
- [**CRITICAL**] **FARIDABAD** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 8.97%: 78.00 (Mar 2024) -> 7.00 (Jun 2024)
- [**CRITICAL**] **FATEHABAD** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 7.57%: 846.00 (Sep 2025) -> 64.00 (Dec 2025)
- [**CRITICAL**] **GURUGRAM** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 7.34%: 286.00 (Sep 2025) -> 21.00 (Dec 2025)
- [**CRITICAL**] **GURUGRAM** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 3.12%: 96.00 (Mar 2024) -> 3.00 (Jun 2024)
- [**CRITICAL**] **HISAR** | `hsfdc_sponsored` @ Jun 2024: Value dropped to 2.78%: 1,078.00 (Mar 2024) -> 30.00 (Jun 2024)
- [**CRITICAL**] **JHAJJAR** | `hsfdc_sponsored` @ Jun 2024: Value dropped to 6.28%: 733.00 (Mar 2024) -> 46.00 (Jun 2024)
- [**CRITICAL**] **JIND** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 3.45%: 928.00 (Sep 2025) -> 32.00 (Dec 2025)
- [**CRITICAL**] **JIND** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 0.57%: 176.00 (Mar 2024) -> 1.00 (Jun 2024)
- [**CRITICAL**] **JIND** | `hsfdc_sanctioned` @ Jun 2025: Value jumped 20.0x: 1.00 (Mar 2025) -> 20.00 (Jun 2025)
- [**CRITICAL**] **KAITHAL** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 4.97%: 785.00 (Sep 2025) -> 39.00 (Dec 2025)
- [**CRITICAL**] **KAITHAL** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 5.84%: 154.00 (Mar 2024) -> 9.00 (Jun 2024)
- [**CRITICAL**] **KURUKSHETRA** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 2.61%: 115.00 (Mar 2024) -> 3.00 (Jun 2024)
- [**CRITICAL**] **NUH** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 6.59%: 167.00 (Sep 2025) -> 11.00 (Dec 2025)
- [**CRITICAL**] **PALWAL** | `hsfdc_sponsored` @ Jun 2024: Value dropped to 0.59%: 339.00 (Mar 2024) -> 2.00 (Jun 2024)
- [**CRITICAL**] **PALWAL** | `hsfdc_sponsored` @ Sep 2024: Value jumped 20.5x: 2.00 (Jun 2024) -> 41.00 (Sep 2024)
- [**CRITICAL**] **SIRSA** | `hsfdc_sponsored` @ Jun 2024: Value dropped to 2.53%: 831.00 (Mar 2024) -> 21.00 (Jun 2024)
- [**CRITICAL**] **SIRSA** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 1.06%: 283.00 (Mar 2024) -> 3.00 (Jun 2024)
- [**CRITICAL**] **SIRSA** | `hsfdc_sanctioned` @ Jun 2025: Value jumped 17.0x: 2.00 (Mar 2025) -> 34.00 (Jun 2025)
- [**CRITICAL**] **SONIPAT** | `kcc_ah_applications_received` @ Sep 2023: Value jumped 23.9x: 93.00 (Jun 2023) -> 2,224.00 (Sep 2023)
- [**CRITICAL**] **SONIPAT** | `kcc_ah_applications_accepted` @ Sep 2023: Value jumped 23.7x: 93.00 (Jun 2023) -> 2,200.00 (Sep 2023)
- [**CRITICAL**] **SONIPAT** | `kcc_ah_applications_sanctioned` @ Sep 2023: Value jumped 23.4x: 93.00 (Jun 2023) -> 2,177.00 (Sep 2023)
- [**CRITICAL**] **SONIPAT** | `hsfdc_sanctioned` @ Jun 2024: Value dropped to 0.99%: 101.00 (Mar 2024) -> 1.00 (Jun 2024)
- [**CRITICAL**] **YAMUNANAGAR** | `hsfdc_sponsored` @ Dec 2025: Value dropped to 4.69%: 426.00 (Sep 2025) -> 20.00 (Dec 2025)
- [**CRITICAL**] **BHIWANI** | `hsfdc_applications` @ Jun 2024: Value dropped to 8.71%: 1,435.00 (Mar 2024) -> 125.00 (Jun 2024)
- [**CRITICAL**] **FARIDABAD** | `hsfdc_applications` @ Dec 2025: Value dropped to 8.95%: 391.00 (Sep 2025) -> 35.00 (Dec 2025)
- [**CRITICAL**] **FATEHABAD** | `shg_savings_linked_amt` @ Dec 2025: Value dropped to 3.58%: 2.10 (Sep 2023) -> 0.08 (Dec 2025)
- [**CRITICAL**] **GURUGRAM** | `hsfdc_applications` @ Dec 2025: Value dropped to 7.34%: 286.00 (Sep 2025) -> 21.00 (Dec 2025)
- [**CRITICAL**] **HISAR** | `hsfdc_applications` @ Jun 2024: Value dropped to 2.78%: 1,078.00 (Mar 2024) -> 30.00 (Jun 2024)
- [**CRITICAL**] **JHAJJAR** | `hsfdc_applications` @ Jun 2024: Value dropped to 6.28%: 733.00 (Mar 2024) -> 46.00 (Jun 2024)
- [**CRITICAL**] **JHAJJAR** | `shg_savings_linked_amt` @ Dec 2025: Value dropped to 6.10%: 0.77 (Sep 2023) -> 0.05 (Dec 2025)
- [**CRITICAL**] **JIND** | `hsfdc_applications` @ Dec 2025: Value dropped to 6.14%: 928.00 (Sep 2025) -> 57.00 (Dec 2025)
- [**CRITICAL**] **KAITHAL** | `hsfdc_applications` @ Dec 2025: Value dropped to 9.55%: 785.00 (Sep 2025) -> 75.00 (Dec 2025)
- [**CRITICAL**] **KARNAL** | `shg_savings_linked_amt` @ Dec 2025: Value dropped to 8.25%: 5.08 (Sep 2023) -> 0.42 (Dec 2025)
- [**CRITICAL**] **MAHENDRAGARH** | `shg_savings_linked_amt` @ Dec 2025: Value dropped to 0.00%: 1,144.88 (Sep 2023) -> 0.01 (Dec 2025)
- [**CRITICAL**] **MAHENDRAGARH** | `shg_credit_linked_amt` @ Dec 2025: Value dropped to 0.00%: 157,100.27 (Sep 2023) -> 6.02 (Dec 2025)
- [**CRITICAL**] **NUH** | `hsfdc_applications` @ Dec 2025: Value dropped to 6.59%: 167.00 (Sep 2025) -> 11.00 (Dec 2025)
- [**CRITICAL**] **PALWAL** | `hsfdc_applications` @ Jun 2024: Value dropped to 0.59%: 339.00 (Mar 2024) -> 2.00 (Jun 2024)
- [**CRITICAL**] **PALWAL** | `hsfdc_applications` @ Sep 2024: Value jumped 20.5x: 2.00 (Jun 2024) -> 41.00 (Sep 2024)
- [**CRITICAL**] **PANIPAT** | `shg_savings_linked_amt` @ Dec 2025: Value dropped to 8.41%: 1.49 (Sep 2023) -> 0.13 (Dec 2025)
- [**CRITICAL**] **REWARI** | `shg_savings_linked_amt` @ Dec 2025: Value dropped to 0.05%: 525.60 (Sep 2023) -> 0.28 (Dec 2025)
- [**CRITICAL**] **REWARI** | `shg_credit_linked_amt` @ Dec 2025: Value dropped to 0.01%: 69,000.73 (Sep 2023) -> 8.74 (Dec 2025)
- [**CRITICAL**] **ROHTAK** | `shg_credit_linked_no` @ Dec 2025: Value jumped 10.8x: 25.00 (Sep 2023) -> 269.00 (Dec 2025)
- [**CRITICAL**] **SIRSA** | `hsfdc_applications` @ Jun 2024: Value dropped to 2.55%: 825.00 (Mar 2024) -> 21.00 (Jun 2024)

#### Outlier (2 issues)

- [info] **CHARKI DADRI** | `pmjdy_rupay_card` @ Sep 2025: Value 103,847.00 is 3.0 std devs from mean 89,461.73 (stddev=4,754.05)
- [info] **KAITHAL** | `hsfdc_sponsored` @ Dec 2025: Value 39.00 is 3.0 std devs from mean 653.08 (stddev=201.89)

### Karnataka


#### Missing District (2 issues)

- [WARNING] **Davanagere** | `-` @ June 2024: District missing from this period but present in adjacent periods
- [WARNING] **Davanagere** | `-` @ September 2024: District missing from this period but present in adjacent periods

### Kerala


#### Missing District (1 issues)

- [WARNING] **Kasargod** | `-` @ March 2025: District missing from this period but present in adjacent periods

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 1 quarter(s): September 2020

### Manipur


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 3 quarter(s): March 2016, June 2016, September 2016

### Mizoram


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 15 quarter(s): June 2015, September 2015, December 2015, March 2016, June 2016, December 2016, March 2018, June 2018, September 2018, December 2018 ...and 5 more

### Nagaland


#### Missing District (1 issues)

- [WARNING] **Noklak** | `-` @ September 2021: District missing from this period but present in adjacent periods

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 2 quarter(s): December 2019, March 2020

### Odisha


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 1 quarter(s): June 2024

### Sikkim


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 3 quarter(s): December 2023, March 2024, December 2024

### Tripura


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 3 quarter(s): June 2017, September 2017, June 2019

### West Bengal


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 2 quarter(s): June 2020, September 2023
