# Project FINER - Data Validation Report

Generated: 2026-07-22 00:25:03

States processed: 31
Total issues: **192** (Critical: 14, Warning: 178, Info: 0)

## Summary by State and Issue Type

| State | 10x_jump | column_shift | missing_district | period_gap | Total |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | - | - | 5 | 1 | 6 |
| arunachal-pradesh | - | - | 1 | 1 | 2 |
| assam | - | - | 2 | - | 2 |
| bihar | - | - | - | 1 | 1 |
| chhattisgarh | - | - | - | - | 0 |
| delhi | - | - | - | - | 0 |
| goa | - | - | - | - | 0 |
| gujarat | - | - | - | - | 0 |
| haryana | - | - | - | 1 | 1 |
| himachal-pradesh | 13 | 1 | - | 1 | 15 |
| jammu-kashmir | - | - | - | 1 | 1 |
| jharkhand | - | - | - | - | 0 |
| karnataka | - | - | - | 1 | 1 |
| kerala | - | - | 5 | 1 | 6 |
| ladakh | - | - | - | - | 0 |
| madhya-pradesh | - | - | - | 1 | 1 |
| maharashtra | - | - | - | - | 0 |
| manipur | - | - | - | 1 | 1 |
| meghalaya | - | - | - | - | 0 |
| mizoram | - | - | - | 1 | 1 |
| nagaland | - | - | 1 | 1 | 2 |
| odisha | - | - | - | 1 | 1 |
| punjab | - | - | - | 1 | 1 |
| rajasthan | - | - | 14 | 1 | 15 |
| sikkim | - | - | - | 1 | 1 |
| tamil-nadu | - | - | - | - | 0 |
| telangana | - | - | - | - | 0 |
| tripura | - | - | - | 1 | 1 |
| uttar-pradesh | - | - | 130 | 1 | 131 |
| uttarakhand | - | - | - | 1 | 1 |
| west-bengal | - | - | - | 1 | 1 |

## Detailed Findings


### Andhra Pradesh


#### Missing District (5 issues)

- [WARNING] **Visakhapatanam** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **Vizianagaram** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **West Godavari** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **Y.s.r.** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **Anantapur** | `-` @ March 2022: District missing from this period but present in adjacent periods

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

### Bihar


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 32 quarter(s): June 2016, September 2016, December 2016, March 2017, June 2017, September 2017, December 2017, March 2018, June 2018, September 2018 ...and 22 more

### Haryana


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 8 quarter(s): September 2015, March 2016, June 2018, September 2018, December 2018, March 2019, September 2019, September 2020

### Himachal Pradesh


#### 10X Jump (13 issues)

- [**CRITICAL**] **Bilaspur** | `shg__jlg_disbursement_amt` @ March 2026: Value dropped to 8.35%: 2,795.79 (December 2025) -> 233.33 (March 2026)
- [**CRITICAL**] **Bilaspur** | `shg__jlg_outstanding_no` @ March 2026: Value dropped to 7.88%: 2,803.00 (December 2025) -> 221.00 (March 2026)
- [**CRITICAL**] **Bilaspur** | `shg__jlg_outstanding_amt` @ March 2026: Value dropped to 4.44%: 5,172.32 (December 2025) -> 229.82 (March 2026)
- [**CRITICAL**] **Chamba** | `standup_india__st_sanctioned_amt` @ March 2026: Value dropped to 0.42%: 119.55 (December 2025) -> 0.50 (March 2026)
- [**CRITICAL**] **Hamirpur** | `kcc__kcc_fish_issued_during_quarter_amt` @ March 2026: Value dropped to 7.37%: 10.58 (December 2025) -> 0.78 (March 2026)
- [**CRITICAL**] **Kullu** | `kcc__kcc_fish_issued_during_quarter_amt` @ March 2026: Value jumped 11.2x: 0.95 (December 2025) -> 10.65 (March 2026)
- [**CRITICAL**] **Lahul and Spiti** | `shg__current_fy_savings_linked_amt` @ March 2026: Value jumped 11.6x: 0.79 (December 2025) -> 9.15 (March 2026)
- [**CRITICAL**] **Lahul and Spiti** | `shg__jlg_disbursement_no` @ March 2026: Value jumped 13.0x: 1.00 (December 2025) -> 13.00 (March 2026)
- [**CRITICAL**] **Mandi** | `kcc__kcc_fish_issued_during_quarter_amt` @ March 2026: Value dropped to 0.41%: 4.93 (December 2025) -> 0.02 (March 2026)
- [**CRITICAL**] **Shimla** | `kcc__kcc_fish_outstanding_amt` @ March 2026: Value dropped to 5.74%: 42.18 (December 2025) -> 2.42 (March 2026)
- [**CRITICAL**] **Sirmaur** | `kcc__kcc_fish_issued_during_quarter_amt` @ March 2026: Value dropped to 8.02%: 4.86 (December 2025) -> 0.39 (March 2026)
- [**CRITICAL**] **Sirmaur** | `kcc__kcc_fish_outstanding_amt` @ March 2026: Value dropped to 0.84%: 117.95 (December 2025) -> 0.99 (March 2026)
- [**CRITICAL**] **Una** | `shg__savings_linked_amt` @ March 2026: Value dropped to 3.42%: 26.89 (December 2025) -> 0.92 (March 2026)

#### Column Shift (1 issues)

- [**CRITICAL**] **Kullu** | `branch_network` @ March 2026: 1 field pair(s) in category 'branch_network' appear to have swapped values

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 44 quarter(s): December 2013, March 2014, June 2014, December 2014, March 2015, June 2015, September 2015, December 2015, March 2016, June 2016 ...and 34 more

### Jammu Kashmir


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 8 quarter(s): December 2022, March 2023, June 2023, June 2024, September 2024, December 2024, June 2025, September 2025

### Karnataka


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 2 quarter(s): September 2025, December 2025

### Kerala


#### Missing District (5 issues)

- [WARNING] **Kannur** | `-` @ March 2013: District missing from this period but present in adjacent periods
- [WARNING] **Malappuram** | `-` @ March 2013: District missing from this period but present in adjacent periods
- [WARNING] **Palakkad** | `-` @ March 2013: District missing from this period but present in adjacent periods
- [WARNING] **Thrissur** | `-` @ March 2013: District missing from this period but present in adjacent periods
- [WARNING] **Wayanad** | `-` @ March 2013: District missing from this period but present in adjacent periods

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 32 quarter(s): June 2011, December 2011, March 2012, June 2012, December 2012, June 2013, December 2013, March 2014, June 2014, September 2014 ...and 22 more

### Madhya Pradesh


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 22 quarter(s): June 2017, September 2017, December 2017, March 2018, June 2018, September 2018, December 2018, March 2019, June 2019, September 2019 ...and 12 more

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

### Punjab


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 3 quarter(s): June 2021, March 2024, September 2025

### Rajasthan


#### Missing District (14 issues)

- [WARNING] **Ganganagar** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Karauli** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Kota** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Kota** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Nagaur** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Nagaur** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Pali** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Pratapgarh** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Rajsamand** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Sawai Madhopur** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Sikar** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Sirohi** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Tonk** | `-` @ March 2021: District missing from this period but present in adjacent periods
- [WARNING] **Udaipur** | `-` @ March 2021: District missing from this period but present in adjacent periods

#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 16 quarter(s): March 2014, June 2014, March 2015, December 2016, June 2017, December 2017, September 2018, December 2018, March 2019, June 2019 ...and 6 more

### Sikkim


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 3 quarter(s): December 2023, March 2024, December 2024

### Tripura


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 1 quarter(s): June 2017

### Uttar Pradesh


#### Missing District (130 issues)

- [WARNING] **Agra** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Agra** | `-` @ December 2022: District missing from this period but present in adjacent periods
- [WARNING] **Agra** | `-` @ September 2024: District missing from this period but present in adjacent periods
- [WARNING] **Aligarh** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Aligarh** | `-` @ June 2023: District missing from this period but present in adjacent periods
- [WARNING] **Aligarh** | `-` @ December 2023: District missing from this period but present in adjacent periods
- [WARNING] **Ambedkar Nagar** | `-` @ September 2022: District missing from this period but present in adjacent periods
- [WARNING] **Ambedkar Nagar** | `-` @ December 2023: District missing from this period but present in adjacent periods
- [WARNING] **Ambedkar Nagar** | `-` @ September 2024: District missing from this period but present in adjacent periods
- [WARNING] **Ambedkar Nagar** | `-` @ December 2024: District missing from this period but present in adjacent periods
- [WARNING] **Amethi** | `-` @ June 2019: District missing from this period but present in adjacent periods
- [WARNING] **Amethi** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Amethi** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Amethi** | `-` @ June 2023: District missing from this period but present in adjacent periods
- [WARNING] **Amethi** | `-` @ December 2024: District missing from this period but present in adjacent periods
- [WARNING] **Amroha** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Amroha** | `-` @ September 2023: District missing from this period but present in adjacent periods
- [WARNING] **Amroha** | `-` @ December 2023: District missing from this period but present in adjacent periods
- [WARNING] **Amroha** | `-` @ June 2024: District missing from this period but present in adjacent periods
- [WARNING] **Auraiya** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Auraiya** | `-` @ June 2024: District missing from this period but present in adjacent periods
- [WARNING] **Azamgarh** | `-` @ June 2022: District missing from this period but present in adjacent periods
- [WARNING] **Azamgarh** | `-` @ September 2022: District missing from this period but present in adjacent periods
- [WARNING] **Azamgarh** | `-` @ June 2023: District missing from this period but present in adjacent periods
- [WARNING] **Baghpat** | `-` @ September 2021: District missing from this period but present in adjacent periods
- [WARNING] **Baghpat** | `-` @ September 2022: District missing from this period but present in adjacent periods
- [WARNING] **Bahraich** | `-` @ June 2019: District missing from this period but present in adjacent periods
- [WARNING] **Bahraich** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Bahraich** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Bahraich** | `-` @ December 2023: District missing from this period but present in adjacent periods
- [WARNING] **Bahraich** | `-` @ March 2024: District missing from this period but present in adjacent periods
- [WARNING] **Ballia** | `-` @ June 2022: District missing from this period but present in adjacent periods
- [WARNING] **Ballia** | `-` @ March 2024: District missing from this period but present in adjacent periods
- [WARNING] **Balrampur** | `-` @ June 2022: District missing from this period but present in adjacent periods
- [WARNING] **Banda** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Barabanki** | `-` @ March 2019: District missing from this period but present in adjacent periods
- [WARNING] **Barabanki** | `-` @ June 2019: District missing from this period but present in adjacent periods
- [WARNING] **Barabanki** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Barabanki** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Bareilly** | `-` @ September 2021: District missing from this period but present in adjacent periods
- [WARNING] **Bareilly** | `-` @ June 2022: District missing from this period but present in adjacent periods
- [WARNING] **Basti** | `-` @ June 2019: District missing from this period but present in adjacent periods
- [WARNING] **Basti** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Bhadohi** | `-` @ June 2021: District missing from this period but present in adjacent periods
- [WARNING] **Bhadohi** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Bhadohi** | `-` @ March 2022: District missing from this period but present in adjacent periods
- [WARNING] **Bijnor** | `-` @ June 2019: District missing from this period but present in adjacent periods
- [WARNING] **Bijnor** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Budaun** | `-` @ December 2021: District missing from this period but present in adjacent periods
- [WARNING] **Budaun** | `-` @ September 2022: District missing from this period but present in adjacent periods

*...and 80 more issues of this type (run with --verbose for full output)*


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 3 quarter(s): March 2023, March 2025, June 2025

### Uttarakhand


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 6 quarter(s): June 2019, September 2019, December 2019, June 2020, September 2020, December 2021

### West Bengal


#### Period Gap (1 issues)

- [WARNING] **ALL** | `-` @ ALL: Missing 2 quarter(s): June 2020, September 2023
