"""A/B test analysis: Cookie Cats (gate at level 30 = control A, level 40 = treatment B).

Checks, in the order an analyst should run them:
  1. Sample ratio mismatch (SRM): were users really split ~50/50? If not, the split itself
     may be biased and results need caution.
  2. Primary metrics (1-day and 7-day retention): difference, 95% confidence interval,
     two-proportion z-test, plus a bootstrap interval as a cross-check.
  3. Power: the smallest effect this sample could reliably detect (minimum detectable effect).
  4. Guardrail metric (game rounds played): heavily skewed, so compare medians with a
     Mann-Whitney U test rather than means.
"""
import numpy as np
import pandas as pd
from scipy import stats

import config as C


def srm_test(n_a: int, n_b: int) -> dict:
    expected = (n_a + n_b) / 2
    chi2 = ((n_a - expected) ** 2 + (n_b - expected) ** 2) / expected
    p = float(stats.chi2.sf(chi2, df=1))
    return {"n_a": n_a, "n_b": n_b, "share_a": n_a / (n_a + n_b), "chi2": chi2, "p_value": p,
            "srm_flag": p < 0.01}


def two_prop_test(x_a: int, n_a: int, x_b: int, n_b: int, alpha: float = C.ALPHA) -> dict:
    p_a, p_b = x_a / n_a, x_b / n_b
    pooled = (x_a + x_b) / (n_a + n_b)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / se_pooled
    p_value = float(2 * stats.norm.sf(abs(z)))
    se = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)       # unpooled SE for the CI
    zc = stats.norm.isf(alpha / 2)
    d = p_b - p_a
    return {"rate_a": p_a, "rate_b": p_b, "diff_pp": 100 * d, "rel_change_pct": 100 * d / p_a,
            "ci_low_pp": 100 * (d - zc * se), "ci_high_pp": 100 * (d + zc * se),
            "z": float(z), "p_value": p_value, "significant": p_value < alpha}


def mde(p_base: float, n_per_group: int, alpha: float = C.ALPHA, power: float = C.POWER) -> float:
    """Minimum detectable effect (absolute, in percentage points) for a two-proportion test."""
    z = stats.norm.isf(alpha / 2) + stats.norm.ppf(power)
    return float(100 * z * np.sqrt(2 * p_base * (1 - p_base) / n_per_group))


def bootstrap_diff(a: np.ndarray, b: np.ndarray, draws: int = C.BOOTSTRAP_DRAWS, seed: int = C.SEED) -> tuple:
    rng = np.random.default_rng(seed)
    diffs = np.empty(draws)
    for i in range(draws):
        diffs[i] = rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return 100 * lo, 100 * hi, float((diffs > 0).mean())


def analyse(ab: pd.DataFrame) -> dict:
    ab = ab.copy()
    for col in ["retention_1", "retention_7"]:
        ab[col] = ab[col].astype(str).str.lower().isin(["true", "1"])
    a, b = ab[ab["version"] == "gate_30"], ab[ab["version"] == "gate_40"]
    out = {"srm": srm_test(len(a), len(b)), "metrics": {}}
    for col in ["retention_1", "retention_7"]:
        t = two_prop_test(int(a[col].sum()), len(a), int(b[col].sum()), len(b))
        t["boot_ci_low_pp"], t["boot_ci_high_pp"], t["prob_b_better"] = bootstrap_diff(
            a[col].to_numpy(float), b[col].to_numpy(float))
        t["mde_pp"] = mde(t["rate_a"], min(len(a), len(b)))
        out["metrics"][col] = t
    g_a, g_b = a["sum_gamerounds"], b["sum_gamerounds"]
    u = stats.mannwhitneyu(g_a, g_b, alternative="two-sided")
    out["guardrail"] = {"median_a": float(g_a.median()), "median_b": float(g_b.median()),
                        "mean_a": float(g_a.mean()), "mean_b": float(g_b.mean()),
                        "max_rounds": int(ab["sum_gamerounds"].max()), "mw_p_value": float(u.pvalue)}
    return out


def results_table(res: dict) -> pd.DataFrame:
    rows = []
    for col, t in res["metrics"].items():
        rows.append({"metric": col, "control_gate_30": round(100 * t["rate_a"], 2),
                     "treatment_gate_40": round(100 * t["rate_b"], 2), "diff_pp": round(t["diff_pp"], 2),
                     "ci_95_pp": f"[{t['ci_low_pp']:.2f}, {t['ci_high_pp']:.2f}]",
                     "bootstrap_ci_pp": f"[{t['boot_ci_low_pp']:.2f}, {t['boot_ci_high_pp']:.2f}]",
                     "p_value": round(t["p_value"], 4), "mde_pp": round(t["mde_pp"], 2),
                     "significant": t["significant"]})
    return pd.DataFrame(rows)
