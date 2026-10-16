"""Step 1 - Get and clean the data.

Online Retail II (UCI): ~1M invoice lines from a UK online shop, Dec 2009 - Dec 2011.
Cleaning rules (each counted in outputs/data_quality.csv):
  * cancellations   - invoice number starts with 'C' (returns/refunds)
  * missing_customer - no Customer ID, so the line can't be used for customer analysis
  * bad_quantity_or_price - quantity <= 0 or price <= 0 (adjustments, bad debt, samples)
  * duplicates      - exact duplicate lines
Clean lines are saved as data/processed/transactions.parquet (small enough to commit).
"""
import io
import zipfile

import pandas as pd
import requests

import config as C


def download_retail() -> None:
    if C.RETAIL_XLSX.exists():
        print(f"  exists, skipping: {C.RETAIL_XLSX.name}")
        return
    print("  downloading Online Retail II from UCI ...")
    r = requests.get(C.RETAIL_URL, timeout=300)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".xlsx")][0]
        C.RETAIL_XLSX.write_bytes(z.read(name))
    print(f"  saved {C.RETAIL_XLSX.name}")


def load_raw() -> pd.DataFrame:
    sheets = pd.read_excel(C.RETAIL_XLSX, sheet_name=None, dtype={"Invoice": str, "StockCode": str})
    return pd.concat(sheets.values(), ignore_index=True)


def clean(raw: pd.DataFrame) -> tuple:
    df = raw.rename(columns={"Customer ID": "customer_id", "InvoiceDate": "invoice_date",
                             "Invoice": "invoice", "StockCode": "stock_code", "Description": "description",
                             "Quantity": "quantity", "Price": "price", "Country": "country"}).copy()
    df["invoice"] = df["invoice"].astype(str)
    total = len(df)
    checks = {
        "cancellations": df["invoice"].str.upper().str.startswith("C"),
        "missing_customer": df["customer_id"].isna(),
        "bad_quantity_or_price": (df["quantity"] <= 0) | (df["price"] <= 0),
        "duplicates": df.duplicated(),
    }
    dq = pd.DataFrame([{"rule": k, "rows": int(v.sum()), "pct_of_raw": round(100 * v.mean(), 2)}
                       for k, v in checks.items()])
    bad = pd.concat(checks.values(), axis=1).any(axis=1)
    out = df[~bad].copy()
    out["customer_id"] = out["customer_id"].astype(int)
    out["invoice_date"] = pd.to_datetime(out["invoice_date"])
    out["revenue"] = (out["quantity"] * out["price"]).round(2)
    out = out[["invoice", "invoice_date", "customer_id", "country", "stock_code", "description",
               "quantity", "price", "revenue"]]
    summary = {"raw_rows": total, "clean_rows": len(out), "removed_rows": int(bad.sum()),
               "removed_pct": round(100 * bad.mean(), 2)}
    return out, dq, summary


def main() -> None:
    C.RAW.mkdir(parents=True, exist_ok=True)
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    C.OUTPUTS.mkdir(exist_ok=True)
    print("Prepare")
    if C.RETAIL_PARQUET.exists() and not C.RETAIL_XLSX.exists():
        print("  using committed data/processed/transactions.parquet")
    else:
        download_retail()
        tx, dq, s = clean(load_raw())
        tx.to_parquet(C.RETAIL_PARQUET, index=False)
        dq.to_csv(C.OUTPUTS / "data_quality.csv", index=False)
        pd.DataFrame([s]).to_csv(C.OUTPUTS / "data_quality_summary.csv", index=False)
        print(f"  {s['raw_rows']:,} raw lines -> {s['clean_rows']:,} clean ({s['removed_pct']}% removed)")
    if C.AB_CSV.exists():
        ab = pd.read_csv(C.AB_CSV)
        ab.to_csv(C.AB_PROCESSED, index=False)
    if not C.AB_PROCESSED.exists():
        raise SystemExit(f"A/B data missing: download cookie_cats.csv from Kaggle into {C.RAW}")


if __name__ == "__main__":
    main()
