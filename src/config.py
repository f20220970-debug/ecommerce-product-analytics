"""Settings for the product analytics project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
CHARTS = OUTPUTS / "charts"
REPORTS = ROOT / "reports"

RETAIL_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
RETAIL_XLSX = RAW / "online_retail_II.xlsx"
RETAIL_PARQUET = PROCESSED / "transactions.parquet"
AB_CSV = RAW / "cookie_cats.csv"                 # Kaggle: "Mobile Games A/B Testing" (Cookie Cats)
AB_PROCESSED = PROCESSED / "cookie_cats.csv"     # committed copy so CI can run

# A/B test settings
ALPHA = 0.05          # significance level
POWER = 0.80          # target power for the minimum-detectable-effect calculation
BOOTSTRAP_DRAWS = 2000
SEED = 42
