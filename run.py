"""Run everything: prepare data -> KPIs, cohorts, RFM -> A/B test -> charts -> report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd  # noqa: E402

import abtest  # noqa: E402
import charts  # noqa: E402
import config as C  # noqa: E402
import metrics as M  # noqa: E402
import prepare  # noqa: E402

MARK = "<!-- COMMENTARY -->"


def md(df):
    h = "| " + " | ".join(map(str, df.columns)) + " |"
    s = "| " + " | ".join("---" for _ in df.columns) + " |"
    return "\n".join([h, s] + ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)])


def kept(path):
    default = "_Write 4-6 sentences in your own words: what drives revenue, how well customers are retained, which segments matter, what the A/B test says and what you'd recommend._"
    if path.exists():
        parts = path.read_text(encoding="utf-8").split(MARK)
        if len(parts) == 3:
            return parts[1].strip()
    return default


def main():
    prepare.main()
    tx = pd.read_parquet(C.RETAIL_PARQUET)
    o = M.orders(tx)
    k = M.monthly_kpis(o)
    ret = M.cohort_retention(o)
    r = M.rfm(o)
    seg = M.segment_summary(r)
    pareto = M.pareto_share(r)
    ab = pd.read_csv(C.AB_PROCESSED)
    res = abtest.analyse(ab)
    abt = abtest.results_table(res)

    k.to_csv(C.OUTPUTS / "monthly_kpis.csv", index=False)
    ret.round(4).to_csv(C.OUTPUTS / "cohort_retention.csv")
    r.reset_index().to_csv(C.OUTPUTS / "rfm_customers.csv", index=False)
    seg.to_csv(C.OUTPUTS / "rfm_segments.csv", index=False)
    abt.to_csv(C.OUTPUTS / "ab_test_results.csv", index=False)
    charts.monthly(k); charts.cohort_heatmap(ret); charts.segments(seg); charts.ab_chart(res)

    # headline numbers
    m1 = ret[1].mean() if 1 in ret.columns else float("nan")
    m3 = ret[3].mean() if 3 in ret.columns else float("nan")
    repeat = (r["frequency"] > 1).mean()
    srm = res["srm"]; r1 = res["metrics"]["retention_1"]; r7 = res["metrics"]["retention_7"]; g = res["guardrail"]
    dq_path = C.OUTPUTS / "data_quality.csv"
    dq = pd.read_csv(dq_path) if dq_path.exists() else None
    dqs = pd.read_csv(C.OUTPUTS / "data_quality_summary.csv").iloc[0] if (C.OUTPUTS / "data_quality_summary.csv").exists() else None

    facts = [
        f"{len(tx):,} clean order lines, {o['invoice'].nunique():,} orders, {r.shape[0]:,} customers, {k['month'].iloc[0]} to {k['month'].iloc[-1]}; total revenue £{o['revenue'].sum():,.0f}.",
        f"Average order value £{o['revenue'].mean():,.0f}; {100 * repeat:.1f}% of customers ordered more than once.",
        f"Cohort retention: on average {100 * m1:.1f}% of a cohort buys again in month 1 and {100 * m3:.1f}% in month 3.",
        f"The top 20% of customers bring {100 * pareto:.1f}% of revenue; '{seg.iloc[0]['segment']}' is the biggest segment by revenue ({100 * seg.iloc[0]['revenue_share']:.1f}% of revenue from {100 * seg.iloc[0]['customer_share']:.1f}% of customers).",
        f"A/B split: {srm['n_a']:,} vs {srm['n_b']:,} users (SRM p = {srm['p_value']:.4f}{', mismatch flagged' if srm['srm_flag'] else ''}).",
        f"7-day retention: {100 * r7['rate_a']:.2f}% (gate 30) vs {100 * r7['rate_b']:.2f}% (gate 40), diff {r7['diff_pp']:+.2f} pp, 95% CI [{r7['ci_low_pp']:.2f}, {r7['ci_high_pp']:.2f}], p = {r7['p_value']:.4f}.",
        f"1-day retention: diff {r1['diff_pp']:+.2f} pp, p = {r1['p_value']:.4f}; minimum detectable effect at this sample size ≈ {r1['mde_pp']:.2f} pp.",
        f"Guardrail (game rounds): median {g['median_a']:.0f} vs {g['median_b']:.0f}, Mann-Whitney p = {g['mw_p_value']:.4f}; max rounds by one user = {g['max_rounds']:,}; the metric is heavily skewed, so medians are compared, not means.",
    ]
    out = C.REPORTS / "analytics_report.md"
    commentary = kept(out)
    dq_text = (f"{int(dqs['raw_rows']):,} raw lines → {int(dqs['clean_rows']):,} clean ({dqs['removed_pct']}% removed).\n\n" + md(dq)) if dq is not None and dqs is not None else "_Data-quality table is produced when the raw file is processed._"
    text = f"""# E-commerce Product Analytics Report

## 1. Key findings
""" + "\n".join(f"- {f}" for f in facts) + f"""

### Analyst commentary
{MARK}
{commentary}
{MARK}

## 2. Data quality
{dq_text}

## 3. Monthly KPIs (last 6 months)
{md(k.tail(6)[['month', 'revenue', 'orders', 'active_customers', 'new_customers', 'aov', 'new_customer_share']].round(2))}

![Monthly KPIs](../outputs/charts/monthly_kpis.png)

## 4. Cohort retention
![Cohort retention](../outputs/charts/cohort_retention.png)

## 5. RFM segments
{md(seg[['segment', 'customers', 'customer_share', 'revenue_share', 'avg_orders', 'avg_recency_days']].round(3))}

![RFM segments](../outputs/charts/rfm_segments.png)

## 6. A/B test: Cookie Cats (gate at level 30 vs 40)
Sample ratio check: {srm['n_a']:,} vs {srm['n_b']:,} (A share {100 * srm['share_a']:.2f}%), chi-square p = {srm['p_value']:.4f}.

{md(abt)}

Guardrail, game rounds: median {g['median_a']:.0f} (A) vs {g['median_b']:.0f} (B), Mann-Whitney p = {g['mw_p_value']:.4f}.

![A/B test](../outputs/charts/ab_test.png)

## 7. Method notes
- Cancellations, lines without a customer, non-positive quantities or prices and duplicates are removed before analysis and counted above.
- Cohort = month of a customer's first order; retention = share of the cohort ordering in a later month. The most recent cohorts have fewer months of history.
- RFM: recency (days since last order), frequency (orders) and monetary (revenue) scored 1-5 by quintile; segments are rule-based on R and F.
- A/B: two-proportion z-test with a 95% confidence interval, a bootstrap interval as a cross-check, a sample-ratio-mismatch check, a minimum-detectable-effect calculation at 80% power, and a Mann-Whitney test on the skewed guardrail metric.
"""
    out.write_text(text, encoding="utf-8")
    print("Analysis")
    for f in facts:
        print("  -", f)


if __name__ == "__main__":
    main()
