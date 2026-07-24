"""Pure-logic tests for the verification harness. No PDFs, no network.

    python3 audit/test_verify.py
"""
import verify as V


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_error_rate_math():
    check(abs(V.rule_of_three_upper(60) - 0.05) < 1e-9, "3/60 = 5%")
    check(abs(V.rule_of_three_upper(30) - 0.10) < 1e-9, "3/30 = 10%")
    # zero errors: Wilson UB is below the rule-of-three approximation, both small
    check(V.wilson_upper(0, 60) < 0.07, "0/60 wilson < 7%")
    # a real error rate lifts the bound well above zero
    check(V.wilson_upper(3, 60) > 0.10, "3/60 wilson upper > 10%")
    check(V.wilson_upper(0, 0) == 1.0, "no data -> unbounded")


def test_reconcile_ratio():
    roles = V.find_roles(["total_deposit", "total_advances", "overall_cd_ratio"])
    good = {"total_deposit": "1000", "total_advances": "600", "overall_cd_ratio": "60"}
    bad = {"total_deposit": "1000", "total_advances": "600", "overall_cd_ratio": "35"}
    checks = dict((c, ok) for c, ok, _ in V.reconcile_row(good, roles))
    check(checks["ratio"] is True, "600/1000=60% matches cdr 60")
    checks = dict((c, ok) for c, ok, _ in V.reconcile_row(bad, roles))
    check(checks["ratio"] is False, "600/1000=60% contradicts cdr 35")


def test_reconcile_area_and_pct():
    roles = V.find_roles(["total_deposit", "dep_rural", "dep_semi_urban", "dep_urban"])
    ok_row = {"total_deposit": "300", "dep_rural": "100", "dep_semi_urban": "100", "dep_urban": "100"}
    check(dict((c, o) for c, o, _ in V.reconcile_row(ok_row, roles))["dep_area_sum"], "100+100+100=300")
    bad_row = {"total_deposit": "300", "dep_rural": "100", "dep_semi_urban": "100", "dep_urban": "50"}
    check(not dict((c, o) for c, o, _ in V.reconcile_row(bad_row, roles))["dep_area_sum"], "250 != 300")
    # achievement% : a/target*100 == pct  (the Odisha check)
    roles = V.find_roles(["total_msme_t", "a", "pct"])
    row = {"total_msme_t": "2406.87", "a": "3085.19", "pct": "128.18"}
    check(dict((c, o) for c, o, _ in V.reconcile_row(row, roles))["achievement_pct"], "3085/2407=128.2")


def test_diff_tables():
    pub = [{"quarter": "March 2024", "district": "Angul", "column": "dep", "value": "1000"},
           {"quarter": "March 2024", "district": "Balasore", "column": "dep", "value": "2000"}]
    sec = [{"quarter": "March 2024", "district": "Angul", "column": "dep", "value": "1000.3"},
           {"quarter": "March 2024", "district": "Balasore", "column": "dep", "value": "2500"}]
    d = V.diff_tables(pub, sec)
    check(d["agree"] == 1 and d["disagree"] == 1, "one within tol, one off")
    check(d["mismatches"][0]["key"][1] == "Balasore", "Balasore flagged")


def test_sampler_stratifies():
    complete = {"quarters": {
        f"2024-0{q}": {"period": f"P{q}", "tables": {"cat": {
            "fields": ["district", "a", "pct", "total_t"],
            "districts": {f"d{i}": {"district": f"d{i}", "a": str(i * 100),
                                    "pct": str(i), "total_t": str(i * 50)} for i in range(1, 6)}}}}
        for q in range(1, 4)}}
    s = V.sample_table(complete, "cat", tier="C", seed=1)
    strata = {c["stratum"] for c in s}
    check(len(s) <= V.TIER_N["C"], "respects tier cap")
    check("per_quarter" in strata and "high_magnitude" in strata, "includes key strata")
    check(V.sample_table(complete, "cat", "C", seed=1) == s, "deterministic with seed")


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
            n += 1
    print(f"\n{n} test groups passed")
