# AWS setup guide: Cloud-Based Customer Risk & Churn Prediction Platform

Follow these steps in order. First time through takes about 4–6 hours.
Cost: a few cents to about €1 if you delete resources at the end (Step 9).

## Architecture

```
churn.csv ──> S3 raw/ ──> AWS Glue (PySpark ETL) ──> S3 curated/ (Parquet)
                                                         │
                                       Amazon Athena data warehouse (churn_dw)
                                          │                         ▲
                              SQL analytics + Power BI     score_customers.py
                                                           (trained ML model)
                                                                    │
                                                           S3 predictions/
```

## Step 0: Copy these files into your Churn-Project folder

```
Churn-Project/
├── churn.ipynb, churn.csv, churn_model.pkl, model_columns.pkl, README.md
├── etl/churn_etl_pyspark.py
├── scoring/score_customers.py
├── sql/01_athena_warehouse_setup.sql
├── sql/02_churn_analytics.sql
└── AWS_SETUP.md
```

## Step 1: AWS account safety (10 minutes, do this first)

1. Sign in to the AWS Console. Choose the **eu-west-1 (Ireland)** region (top right) and use it everywhere.
2. **Billing → Budgets → Create budget → Zero spend budget** so you get an email if anything costs money.
3. **IAM → Users → Create user** (e.g. `churn-dev`). Attach `AmazonS3FullAccess`, `AmazonAthenaFullAccess`, `AWSGlueConsoleFullAccess`. Create an **access key** (for CLI).
4. Install the **AWS CLI** and run `aws configure` (paste the key, region `eu-west-1`).
   Never put keys in your code or commit them to GitHub.

## Step 2: S3 data lake (10 minutes)

Create a bucket with a unique name, e.g. `hrithikesh-churn-platform`:

```
aws s3 mb s3://hrithikesh-churn-platform --region eu-west-1
aws s3 cp churn.csv s3://hrithikesh-churn-platform/raw/churn.csv
aws s3 cp etl/churn_etl_pyspark.py s3://hrithikesh-churn-platform/scripts/
```

Folder layout in the bucket: `raw/`, `curated/`, `predictions/`, `scripts/`, `athena-results/`.

## Step 3: IAM role for Glue (10 minutes)

IAM → Roles → Create role → Trusted entity: **Glue**. Attach `AWSGlueServiceRole` and
`AmazonS3FullAccess`. Name it `GlueChurnRole`.

## Step 4: Run the PySpark ETL job on AWS Glue (30 minutes)

1. AWS Glue → **ETL jobs → Script editor → Spark** → "Upload and edit an existing script" → choose `etl/churn_etl_pyspark.py`.
2. **Job details** tab:
   - Name: `churn-etl`
   - IAM role: `GlueChurnRole`
   - Worker type **G.1X**, number of workers **2** (smallest = cheapest)
   - Job timeout: 10 minutes
   - **Job parameters**:
     - `--input` = `s3://hrithikesh-churn-platform/raw/churn.csv`
     - `--output` = `s3://hrithikesh-churn-platform/curated/customer_features/`
3. Save → **Run**. Check **Runs → Output logs** for the row count and churn rate.
4. Confirm Parquet files exist: `aws s3 ls s3://hrithikesh-churn-platform/curated/customer_features/`

Take a screenshot of the successful run for your README.

## Step 5: Athena data warehouse (20 minutes)

1. Athena → Query editor → **Settings** → query result location `s3://hrithikesh-churn-platform/athena-results/`.
2. Open `sql/01_athena_warehouse_setup.sql`, replace `YOUR-BUCKET`, run each statement.
3. `SELECT COUNT(*) FROM churn_dw.customer_features;` should return your row count.

## Step 6: Score customers with your ML model (20 minutes)

In the VS Code terminal (venv active):

```
pip install pandas pyarrow s3fs scikit-learn joblib
python scoring/score_customers.py --input s3://hrithikesh-churn-platform/curated/customer_features/ --output s3://hrithikesh-churn-platform/predictions/predictions.parquet
```

Before running, open `prepare_features()` in the script and make sure it matches your
notebook's preprocessing (get_dummies, any Yes/No mapping, and a saved scaler if you used one).
Sanity check: the model's predictions should be similar to your notebook's test results.

Then in Athena: `SELECT risk_tier, COUNT(*) FROM churn_dw.churn_predictions GROUP BY risk_tier;`

## Step 7: SQL analytics (45 minutes)

Run the 9 queries in `sql/02_churn_analytics.sql`. Write the key answers in the README
under "Key insights" (churn by contract, tenure, payment method, revenue at risk).

## Step 8: Power BI dashboard (1–2 hours)

**Option A – live connection (better for interviews):**
1. Install the **Amazon Athena ODBC driver** (from the AWS Athena docs) and create an ODBC DSN for region `eu-west-1`, output location `s3://hrithikesh-churn-platform/athena-results/`.
2. Power BI Desktop → Get data → **Amazon Athena** → enter the DSN → load `customer_features` and `churn_predictions`.

**Option B – quick:** load `predictions.csv` and `churn.csv` into Power BI directly.

Create a relationship on `customerid`. Build 4 pages:

| Page | Visuals |
|---|---|
| Overview | KPI cards: customers, churn rate, revenue lost, revenue at risk |
| Segments | Churn rate by contract, tenure group, payment method, internet service |
| Model insights | Risk tier distribution, top churn drivers (export coefficients from the notebook as CSV) |
| Action list | Table of high-risk, high-value customers to contact (slicers for contract and tier) |

DAX measures to start with:

```
Churn Rate = DIVIDE(SUM(customer_features[churn_flag]), COUNTROWS(customer_features))
Revenue at Risk = CALCULATE(SUM(churn_predictions[annual_revenue]), churn_predictions[risk_tier] = "High")
High Risk Customers = CALCULATE(COUNTROWS(churn_predictions), churn_predictions[risk_tier] = "High")
```

Export to PDF and save screenshots in `images/` for the README.

To export driver importance from the notebook for the "Model insights" page:

```python
pd.Series(lr.coef_[0], index=x.columns).sort_values().to_csv("images/churn_drivers.csv", header=["coefficient"])
```

## Step 9: Clean up (5 minutes)

- Glue jobs cost nothing when not running; you can keep the job.
- S3 storage for these files is a fraction of a cent. Keep it while job hunting, delete later.
- Delete the IAM access key when you're done, and never commit it.

## README section to add

```markdown
## Architecture
Raw CSV in **Amazon S3** → **AWS Glue (PySpark)** ETL: cleaning and feature engineering →
Parquet in S3 → **Amazon Athena** data warehouse → **SQL analytics** →
**ML model** batch scoring (scikit-learn) → predictions back to the warehouse →
**Power BI** dashboard.

## Tech
Python, SQL, PySpark, Scikit-learn, Machine Learning, ETL, AWS (S3, Glue, Athena),
Data Warehouse, Power BI
```

## How each resume bullet maps to this project

| Resume bullet | Where it is |
|---|---|
| End-to-end cloud data pipeline on AWS with Python, SQL, PySpark | S3 → Glue PySpark job → Athena (Steps 2–5) |
| ETL: cleansing, transformation, feature engineering, load to warehouse | `etl/churn_etl_pyspark.py` |
| ML classification models for churn and high-risk segments | `churn.ipynb` + `scoring/score_customers.py` risk tiers |
| SQL analytics and Python for behaviour patterns and churn factors | `sql/02_churn_analytics.sql` + notebook EDA |
| Power BI dashboards: trends, segments, model insights, revenue at risk | Step 8 dashboard |

Be ready to explain in an interview: why Parquet (columnar, smaller, faster for Athena),
why Glue (serverless Spark, no cluster to manage), and why you chose Logistic Regression
(higher churn recall).
