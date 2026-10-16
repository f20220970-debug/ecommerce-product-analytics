"""Hand-checked tests for the metric and A/B-test functions."""
import numpy as np
import pandas as pd

import abtest
import metrics as M
from prepare import clean


def tx_sample():
    rows = [  # invoice, date, customer, revenue
        ("1", "2024-01-05", 1, 10), ("2", "2024-01-20", 2, 20), ("3", "2024-02-03", 1, 30),
        ("4", "2024-03-10", 3, 40), ("5", "2024-03-15", 1, 50), ("6", "2024-03-20", 2, 60)]
    return pd.DataFrame([{"invoice": i, "invoice_date": pd.Timestamp(d), "customer_id": c, "revenue": r,
                          "country": "UK"} for i, d, c, r in rows])


def test_cohort_retention():
    o = M.orders(tx_sample())
    ret = M.cohort_retention(o)
    jan = ret.loc["2024-01"]
    assert jan["cohort_size"] == 2          # customers 1 and 2 first bought in January
    assert jan[1] == 0.5                    # only customer 1 bought in February
    assert jan[2] == 1.0                    # both bought in March


def test_monthly_kpis_new_vs_returning():
    k = M.monthly_kpis(M.orders(tx_sample())).set_index("month")
    assert k.loc["2024-03", "active_customers"] == 3
    assert k.loc["2024-03", "new_customers"] == 1    # customer 3
    assert k.loc["2024-01", "aov"] == 15


def test_rfm_scores_and_pareto():
    rng = np.random.default_rng(0)
    rows = []
    for c in range(100):
        for j in range(rng.integers(1, 6)):
            rows.append({"invoice": f"{c}-{j}", "invoice_date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 300))),
                         "customer_id": c, "revenue": float(rng.integers(5, 500)), "country": "UK"})
    r = M.rfm(M.orders(pd.DataFrame(rows)))
    assert set(r["R"]) == {1, 2, 3, 4, 5} and r["segment"].notna().all()
    assert 0.2 < M.pareto_share(r) <= 1


def test_clean_rules():
    raw = pd.DataFrame({"Invoice": ["1", "C2", "3", "4", "4"], "StockCode": ["a"] * 5, "Description": ["x"] * 5,
                        "Quantity": [1, -1, 0, 2, 2], "InvoiceDate": ["2024-01-01"] * 5, "Price": [1.0] * 5,
                        "Customer ID": [1, 1, 1, None, None], "Country": ["UK"] * 5})
    out, dq, s = clean(raw)
    assert s["clean_rows"] == 1 and dq.set_index("rule").loc["cancellations", "rows"] == 1


def test_two_prop_and_srm():
    t = abtest.two_prop_test(500, 1000, 550, 1000)
    assert abs(t["diff_pp"] - 5) < 1e-9 and t["ci_low_pp"] < 5 < t["ci_high_pp"]
    assert abtest.srm_test(5000, 5000)["p_value"] > 0.99
    assert abtest.srm_test(4700, 5300)["srm_flag"]


def test_mde_shrinks_with_sample_size():
    assert abtest.mde(0.2, 10_000) < abtest.mde(0.2, 1_000)
