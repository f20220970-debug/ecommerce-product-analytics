"""Charts saved to outputs/charts/ for the README and report."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config as C


def _save(fig, name):
    C.CHARTS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(C.CHARTS / name, dpi=120)
    plt.close(fig)


def monthly(k):
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.bar(k["month"], k["revenue"] / 1e3, color="#2C7A7B")
    ax.set_ylabel("Revenue (thousand £)")
    ax2 = ax.twinx()
    ax2.plot(k["month"], k["active_customers"], color="#C0392B", marker="o", ms=3)
    ax2.set_ylabel("Active customers", color="#C0392B")
    ax.set_xticks(range(0, len(k), 3))
    ax.set_xticklabels(k["month"].iloc[::3], rotation=30, fontsize=8)
    ax.set_title("Monthly revenue and active customers")
    _save(fig, "monthly_kpis.png")


def cohort_heatmap(ret, max_age=12):
    m = ret.drop(columns="cohort_size").iloc[:, : max_age + 1]
    fig, ax = plt.subplots(figsize=(11, 7))
    im = ax.imshow(m.values * 100, cmap="YlGnBu", aspect="auto", vmin=0, vmax=50)
    ax.set_xticks(range(m.shape[1]))
    ax.set_xticklabels([str(c) for c in m.columns])
    ax.set_yticks(range(len(m)))
    ax.set_yticklabels(m.index, fontsize=7)
    for i in range(m.shape[0]):
        for j in range(1, m.shape[1]):
            v = m.values[i, j]
            if not np.isnan(v) and v > 0:
                ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=6)
    ax.set_xlabel("Months since first purchase")
    ax.set_ylabel("Cohort (month of first purchase)")
    ax.set_title("Customer retention by cohort (% of cohort buying again)")
    fig.colorbar(im, ax=ax, label="% retained")
    _save(fig, "cohort_retention.png")


def segments(s):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = np.arange(len(s))
    ax.bar(x - 0.2, 100 * s["customer_share"], 0.4, label="% of customers", color="#9DB4C0")
    ax.bar(x + 0.2, 100 * s["revenue_share"], 0.4, label="% of revenue", color="#1F3A5F")
    ax.set_xticks(x)
    ax.set_xticklabels(s["segment"], rotation=15)
    ax.set_ylabel("%")
    ax.legend()
    ax.set_title("RFM segments: share of customers vs share of revenue")
    _save(fig, "rfm_segments.png")


def ab_chart(res):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, (col, t) in zip(axes, res["metrics"].items()):
        rates = [100 * t["rate_a"], 100 * t["rate_b"]]
        ax.bar(["gate_30 (A)", "gate_40 (B)"], rates, color=["#9DB4C0", "#2C7A7B"])
        for i, v in enumerate(rates):
            ax.text(i, v + 0.3, f"{v:.2f}%", ha="center")
        ax.set_ylim(0, max(rates) * 1.2)
        ax.set_title(f"{col}: diff {t['diff_pp']:+.2f} pp (p = {t['p_value']:.3f})")
    fig.suptitle("Cookie Cats A/B test: retention by version")
    _save(fig, "ab_test.png")
