"""
Batch scoring: read the curated customer table, predict churn with the trained
model, and write predictions back to the data warehouse (S3 / Athena).

  From S3:
    python scoring/score_customers.py ^
        --input  s3://YOUR-BUCKET/curated/customer_features/ ^
        --output s3://YOUR-BUCKET/predictions/predictions.parquet

  Local test (output folder of the ETL job run locally):
    python scoring/score_customers.py --input output/customer_features --output predictions.parquet

Needs: pip install pandas pyarrow s3fs scikit-learn joblib
(s3fs uses the credentials you set up with `aws configure`.)

IMPORTANT: prepare_features() must apply the SAME preprocessing as your
notebook (churn.ipynb). Check the notes inside it.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL_FILE = ROOT / "churn_model.pkl"
COLUMNS_FILE = ROOT / "model_columns.pkl"
SCALER_FILE = ROOT / "scaler.pkl"  # only used if you saved one

# Original column names in churn.csv (the ETL writes them in lower case)
ORIGINAL_COLUMNS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents", "tenure",
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    "MonthlyCharges", "TotalCharges", "Churn",
]


def prepare_features(curated: pd.DataFrame, model_columns: list) -> pd.DataFrame:
    """Turn curated rows into the exact columns the model was trained on.

    This assumes the notebook did: drop customerID and Churn, then
    pd.get_dummies(...). Reindexing to model_columns lines the columns up
    (and handles drop_first=True too).

    If your notebook did something different, copy those steps here, e.g.
      - mapped Yes/No to 1/0 instead of get_dummies
      - created extra features before training
    """
    rename = {c.lower(): c for c in ORIGINAL_COLUMNS}
    df = curated.rename(columns=rename)
    features = [c for c in ORIGINAL_COLUMNS if c not in ("customerID", "Churn")]
    X = pd.get_dummies(df[features])
    X = X.reindex(columns=model_columns, fill_value=0).astype(float)

    if SCALER_FILE.exists():
        scaler = joblib.load(SCALER_FILE)
        X = pd.DataFrame(scaler.transform(X), columns=model_columns, index=X.index)
    return X


def risk_tier(p: float) -> str:
    if p >= 0.7:
        return "High"
    if p >= 0.4:
        return "Medium"
    return "Low"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    model = joblib.load(MODEL_FILE)
    model_columns = joblib.load(COLUMNS_FILE)

    curated = pd.read_parquet(args.input)
    print(f"Scoring {len(curated):,} customers")

    X = prepare_features(curated, model_columns)
    proba = model.predict_proba(X)[:, 1]

    predictions = pd.DataFrame({
        "customerid": curated["customerid"],
        "churn_probability": proba.round(4),
        "risk_tier": [risk_tier(p) for p in proba],
        "monthlycharges": curated["monthlycharges"].round(2),
        "annual_revenue": (curated["monthlycharges"] * 12).round(2),
        "scored_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    })

    predictions.to_parquet(args.output, index=False)
    predictions.to_csv("predictions.csv", index=False)  # handy for Power BI

    summary = predictions.groupby("risk_tier").agg(
        customers=("customerid", "count"),
        annual_revenue=("annual_revenue", "sum"),
    )
    print(summary)
    print(f"Saved predictions to {args.output} and predictions.csv")


if __name__ == "__main__":
    main()
