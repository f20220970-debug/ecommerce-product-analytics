"""Business metrics: monthly KPIs, cohort retention, RFM segmentation."""
import numpy as np
import pandas as pd


def orders(tx: pd.DataFrame) -> pd.DataFrame:
    """One row per order (invoice) with its customer, date and value."""
    o = (tx.groupby("invoice")
           .agg(customer_id=("customer_id", "first"), order_date=("invoice_date", "min"),
                revenue=("revenue", "sum"), country=("country", "first"))
           .reset_index())
    o["month"] = o["order_date"].dt.to_period("M")
    return o


def monthly_kpis(o: pd.DataFrame) -> pd.DataFrame:
    first = o.groupby("customer_id")["month"].min().rename("first_month")
    o = o.join(first, on="customer_id")
    o["is_new"] = o["month"] == o["first_month"]
    g = o.groupby("month")
    k = pd.DataFrame({
        "revenue": g["revenue"].sum(),
        "orders": g["invoice"].nunique(),
        "active_customers": g["customer_id"].nunique(),
        "new_customers": o[o["is_new"]].groupby("month")["customer_id"].nunique(),
    }).fillna(0)
    k["aov"] = k["revenue"] / k["orders"]                       # average order value
    k["orders_per_customer"] = k["orders"] / k["active_customers"]
    k["returning_customers"] = k["active_customers"] - k["new_customers"]
    k["new_customer_share"] = k["new_customers"] / k["active_customers"]
    return k.reset_index().assign(month=lambda x: x["month"].astype(str)).round(4)


def cohort_retention(o: pd.DataFrame) -> pd.DataFrame:
    """Rows = month of first purchase; columns = months since first purchase;
    values = share of the cohort that bought again in that month."""
    first = o.groupby("customer_id")["month"].min().rename("cohort")
    o = o.join(first, on="customer_id")
    o["age"] = (o["month"] - o["cohort"]).apply(lambda d: d.n)
    counts = o.groupby(["cohort", "age"])["customer_id"].nunique().unstack(fill_value=0)
    size = counts[0]
    ret = counts.div(size, axis=0).astype(float)
    last = o["month"].max()
    for cohort in ret.index:                    # months after the data ends are unknown, not zero
        ret.loc[cohort, [a for a in ret.columns if a > (last - cohort).n]] = float("nan")
    ret.insert(0, "cohort_size", size)
    ret.index = ret.index.astype(str)
    return ret


def rfm(o: pd.DataFrame, snapshot=None) -> pd.DataFrame:
    """Recency (days since last order), Frequency (orders), Monetary (revenue), scored 1-5 by quintile."""
    snapshot = snapshot or (o["order_date"].max() + pd.Timedelta(days=1))
    r = o.groupby("customer_id").agg(last=("order_date", "max"), frequency=("invoice", "nunique"),
                                     monetary=("revenue", "sum"))
    r["recency_days"] = (snapshot - r["last"]).dt.days
    # rank first so ties don't break the quintiles; recent = high R score
    r["R"] = pd.qcut(r["recency_days"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    r["F"] = pd.qcut(r["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    r["M"] = pd.qcut(r["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    r["segment"] = r.apply(segment, axis=1)
    return r.drop(columns="last")


def segment(row) -> str:
    R, F = row["R"], row["F"]
    if R >= 4 and F >= 4: return "Champions"
    if R >= 3 and F >= 4: return "Loyal"
    if R == 5 and F == 1: return "New"
    if R >= 4 and F >= 2: return "Potential loyalists"
    if R <= 2 and F >= 3: return "At risk"
    if R <= 2 and F <= 2: return "Hibernating"
    return "Needs attention"


def segment_summary(r: pd.DataFrame) -> pd.DataFrame:
    s = r.groupby("segment").agg(customers=("frequency", "size"), revenue=("monetary", "sum"),
                                 avg_orders=("frequency", "mean"), avg_recency_days=("recency_days", "mean"))
    s["customer_share"] = s["customers"] / s["customers"].sum()
    s["revenue_share"] = s["revenue"] / s["revenue"].sum()
    return s.sort_values("revenue", ascending=False).reset_index().round(4)


def pareto_share(r: pd.DataFrame, top=0.2) -> float:
    """Share of revenue from the top `top` fraction of customers."""
    m = r["monetary"].sort_values(ascending=False)
    k = max(1, int(np.ceil(top * len(m))))
    return float(m.iloc[:k].sum() / m.sum())
