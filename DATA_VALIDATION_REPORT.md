# Project FINER - Data Validation Report

Generated: 2026-05-10 17:13:06

States processed: 23
Total issues: **26** (Critical: 5, Warning: 20, Info: 1)

## Summary by State and Issue Type

| State | 10x_jump | missing_district | outlier | period_gap | Total |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 5 | 5 | 1 | 1 | 12 |
| arunachal-pradesh | - | 1 | - | 1 | 2 |
| assam | - | 2 | - | - | 2 |
| bihar | - | - | - | - | 0 |
| chhattisgarh | - | - | - | - | 0 |
| gujarat | - | - | - | - | 0 |
| haryana | - | - | - | - | 0 |
| jharkhand | - | - | - | - | 0 |
| karnataka | - | - | - | - | 0 |
| kerala | - | - | - | 1 | 1 |
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
| uttarakhand | - | - | - | 1 | 1 |
| west-bengal | - | - | - | 1 | 1 |

## Detailed Findings


### Andhra Pradesh


#### 10X Jump (5 issues)

- [**CRITICAL**] **Visakhapatanam** | `branch_network__branch_urban` @ December 2021: Value dropped to 8.43%: 451.00 (September 2020) -> 38.00 (December 2021)
- [**CRITICAL**] **East Godavari** | `priority_sector__agr_infra` @ June 2021: Value jumped 10.5x: 22.58 (September 2020) -> 236.33 (June 2021)
- [**CRITICAL**] **East Godavari** | `priority_sector__export` @ December 2021: Value dropped to 0.03%: 89.12 (June 2021) -> 0.03 (December 2021)
- [**CRITICAL**] **Spsr Nellore** | `priority_sector__export` @ December 2021: Value dropped to 4.58%: 27.49 (June 2021) -> 1.26 (December 2021)
- [**CRITICAL**] **Y.s.r.** | `priority_sector__ancillary` @ December 2021: Value dropped to 6.67%: 1,402.80 (June 2021) -> 93.50 (December 2021)

#### Missing District (5 issues)

- [WARNING] **Vizianagaram** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **Visakhapatanam** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **West Godavari** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **Y.s.r.** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **Anantapur** | `-` @ March 2022: District missing from this period but present in adjacent periods

#### Outlier (1 issues)

- [info] **Visakhapatanam** | `credit_deposit_ratio__cd_ratio` @ September 2020: Value 200.67 is 3.2 std devs from mean 127.44 (stddev=23.14)

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 5 quarter(s): September 2018, June 2020, December 2020, March 2021, June 2022

### Arunachal Pradesh


#### Missing District (1 issues)

- [WARNING] **Kamle** | `-` @ December 2020: District missing from this period but present in adjacent periods

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 6 quarter(s): June 2018, September 2018, December 2018, March 2019, June 2019, March 2020

### Assam


#### Missing District (2 issues)

- [WARNING] **Dima Hasao** | `-` @ September 2017: District missing from this period but present in adjacent periods
- [WARNING] **Dima Hasao** | `-` @ December 2017: District missing from this period but present in adjacent periods

### Kerala


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

- [WARNING] **ALL** | `-` @ ALL: Missing 1 quarter(s): June 2017

### Uttarakhand


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 6 quarter(s): June 2019, September 2019, December 2019, June 2020, September 2020, December 2021

### West Bengal


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 2 quarter(s): June 2020, September 2023
