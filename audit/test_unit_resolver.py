"""Tests for the unit resolver's PDF-independent tiers: caption parsing and
column-kind classification. Runs anywhere, no source PDFs required.

    python3 audit/test_unit_resolver.py
"""
import unit_resolver as U


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_caption_scale():
    cases = {
        "(Amount in Rs. Crore)": "crore",
        "Amt. in Crores": "crore",
        "Figures in Rs. Cr.": "crore",
        "(Rs. in Lakhs)": "lakh",
        "Amount in Rs. Lacs": "lakh",
        "ALL FIGURES IN LAKH": "lakh",
        "Amount in Rs. '000": "thousand",
        "Rs. in thousands": "thousand",
        "No. in actuals": "actual",
        "Figures in Rs. (absolute)": "actual",
    }
    for text, want in cases.items():
        got = U.parse_unit_caption(text)
        check(got and got["scale"] == want, f"caption {text!r}: want {want}, got {got}")
    # negatives — no monetary scale present
    for text in ["District-wise CD Ratio position", "Number of PMJDY accounts", ""]:
        check(U.parse_unit_caption(text) is None, f"caption {text!r}: expected None")
    # thousand must win over the bare 'lakh'/'crore' word when '000 is present
    check(U.parse_unit_caption("Rs in '000 (lakh omitted)")["scale"] == "thousand", "thousand precedence")


def test_classify_kind():
    money = ["total_deposit", "total_advances", "crop_loan_amt", "total_msme_t",
             "total_ps_target_amt", "disbursement_amt", "outstanding", "npa_amount"]
    count = ["total_branch", "total_pmjdy_no", "no_of_kcc", "total_a_c", "atm",
             "cards_issued", "savings_linked_no", "beneficiaries"]
    percent = ["overall_cd_ratio", "coverage_sb_pct", "achv_pct_amt", "cdr", "c_d_ratio"]
    for c in money:
        check(U.classify_kind(c) == "money", f"{c}: want money, got {U.classify_kind(c)}")
    for c in count:
        check(U.classify_kind(c) == "count", f"{c}: want count, got {U.classify_kind(c)}")
    for c in percent:
        check(U.classify_kind(c) == "percent", f"{c}: want percent, got {U.classify_kind(c)}")


def test_magnitude_fallback():
    # deposit-only (no branch) -> magnitude fallback, size-confounded => capped conf
    def mk(median):
        return {"quarters": {"q": {"tables": {"credit_deposit_ratio": {
            "fields": ["total_deposit"],
            "districts": {f"d{i}": {"total_deposit": str(median + i)} for i in range(9)}}}}}}
    r = U.magnitude_scale(mk(2000))
    check(r["scale"] == "crore" and r["method"] == "deposit_magnitude", "2k -> crore/magnitude")
    check(U.magnitude_scale(mk(500000))["scale"] == "lakh", "500k -> lakh")
    check(U.magnitude_scale(mk(25000))["confidence"] == "low", "25k no-branch -> low (ambiguous)")
    check(U.magnitude_scale({"quarters": {}})["scale"] is None, "no anchor -> None")


def test_deposit_per_branch():
    # deposit + branch -> size-invariant ratio path, disambiguates small states
    def mk(dep, br):
        return {"quarters": {"q": {"tables": {
            "credit_deposit_ratio": {"fields": ["total_deposit"],
                "districts": {f"d{i}": {"total_deposit": str(dep + i)} for i in range(9)}},
            "branch_network": {"fields": ["total_branch"],
                "districts": {f"d{i}": {"total_branch": str(br)} for i in range(9)}}}}}}
    # small state in lakh: dep 16,000 / 6 branches = 2,666 -> lakh (magnitude alone would say crore)
    r = U.magnitude_scale(mk(16000, 6))
    check(r["scale"] == "lakh" and r["method"] == "deposit_per_branch", "small-lakh rescued -> lakh")
    # crore state: dep 4,000 / 100 branches = 40 -> crore, high conf
    r = U.magnitude_scale(mk(4000, 100))
    check(r["scale"] == "crore" and r["confidence"] == "high", "ratio 40 -> crore/high")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
            n += 1
    print(f"\n{n} test groups passed")
