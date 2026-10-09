-- Cloud data warehouse on AWS: Amazon Athena over Parquet files in S3.
-- Replace YOUR-BUCKET with your bucket name, then run each statement
-- in the Athena query editor (one at a time).

CREATE DATABASE IF NOT EXISTS churn_dw;

-- Curated customer table written by the PySpark ETL job
CREATE EXTERNAL TABLE IF NOT EXISTS churn_dw.customer_features (
    customerid          string,
    gender              string,
    seniorcitizen       int,
    partner             string,
    dependents          string,
    tenure              int,
    phoneservice        string,
    multiplelines       string,
    internetservice     string,
    onlinesecurity      string,
    onlinebackup        string,
    deviceprotection    string,
    techsupport         string,
    streamingtv         string,
    streamingmovies     string,
    contract            string,
    paperlessbilling    string,
    paymentmethod       string,
    monthlycharges      double,
    totalcharges        double,
    churn               string,
    churn_flag          int,
    tenure_group        string,
    avg_monthly_spend   double,
    num_services        int,
    is_month_to_month   int,
    has_auto_payment    int,
    annual_revenue      double,
    etl_loaded_at       timestamp
)
STORED AS PARQUET
LOCATION 's3://YOUR-BUCKET/curated/customer_features/';

-- Model predictions written by scoring/score_customers.py
CREATE EXTERNAL TABLE IF NOT EXISTS churn_dw.churn_predictions (
    customerid          string,
    churn_probability   double,
    risk_tier           string,
    monthlycharges      double,
    annual_revenue      double,
    scored_at           string
)
STORED AS PARQUET
LOCATION 's3://YOUR-BUCKET/predictions/';

-- Check it worked
SELECT COUNT(*) AS customers FROM churn_dw.customer_features;
SELECT * FROM churn_dw.churn_predictions LIMIT 10;
