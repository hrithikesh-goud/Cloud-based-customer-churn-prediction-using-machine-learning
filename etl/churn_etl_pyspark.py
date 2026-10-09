"""
PySpark ETL job: raw customer data -> cleaned, feature-engineered table.

Runs as an AWS Glue job (Spark) or locally (e.g. Google Colab).

  AWS Glue job parameters:
    --input   s3://YOUR-BUCKET/raw/churn.csv
    --output  s3://YOUR-BUCKET/curated/customer_features/

  Local / Colab:
    python churn_etl_pyspark.py --input churn.csv --output output/customer_features

Steps
  1. Extract   read the raw CSV
  2. Clean     fix data types, blank TotalCharges, duplicates, missing IDs
  3. Transform engineer churn features
  4. Load      write Parquet (columnar, compressed) for the data warehouse

Column names are written in lower case so Amazon Athena reads them reliably.
"""

import argparse

from pyspark.sql import SparkSession, functions as F

SERVICE_COLUMNS = [
    "PhoneService", "MultipleLines", "OnlineSecurity", "OnlineBackup",
    "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    # Glue passes its own extra arguments (--JOB_NAME etc.); ignore them
    args, _ = parser.parse_known_args()
    return args


def extract(spark, path):
    return spark.read.csv(path, header=True, inferSchema=True)


def clean(df):
    # TotalCharges contains blank strings for brand-new customers
    df = df.withColumn(
        "TotalCharges",
        F.when(F.trim(F.col("TotalCharges").cast("string")) == "", None)
        .otherwise(F.col("TotalCharges"))
        .cast("double"),
    )
    # A new customer's total so far is roughly monthly charge x tenure
    df = df.withColumn(
        "TotalCharges",
        F.coalesce(F.col("TotalCharges"), F.col("MonthlyCharges") * F.col("tenure")),
    )
    df = df.dropna(subset=["customerID", "Churn"]).dropDuplicates(["customerID"])
    df = df.withColumn("SeniorCitizen", F.col("SeniorCitizen").cast("int"))
    return df


def transform(df):
    services_used = sum(
        F.when(F.col(c) == "Yes", 1).otherwise(0) for c in SERVICE_COLUMNS
    )
    df = (
        df.withColumn("churn_flag", (F.col("Churn") == "Yes").cast("int"))
        .withColumn(
            "tenure_group",
            F.when(F.col("tenure") <= 12, "0-12 months")
            .when(F.col("tenure") <= 24, "13-24 months")
            .when(F.col("tenure") <= 48, "25-48 months")
            .otherwise("49+ months"),
        )
        .withColumn(
            "avg_monthly_spend",
            F.round(F.col("TotalCharges") / F.greatest(F.col("tenure"), F.lit(1)), 2),
        )
        .withColumn("num_services", services_used)
        .withColumn(
            "is_month_to_month", (F.col("Contract") == "Month-to-month").cast("int")
        )
        .withColumn(
            "has_auto_payment",
            F.lower(F.col("PaymentMethod")).contains("automatic").cast("int"),
        )
        .withColumn("annual_revenue", F.round(F.col("MonthlyCharges") * 12, 2))
        .withColumn("etl_loaded_at", F.current_timestamp())
    )
    # Lower-case column names for Athena
    return df.toDF(*[c.lower() for c in df.columns])


def quality_report(df):
    total = df.count()
    churned = df.filter(F.col("churn_flag") == 1).count()
    print(f"Rows loaded: {total}")
    print(f"Churn rate: {churned / total:.1%}")
    nulls = df.select(
        [F.sum(F.col(c).isNull().cast("int")).alias(c) for c in df.columns]
    ).first().asDict()
    bad = {c: n for c, n in nulls.items() if n}
    print(f"Columns with nulls: {bad or 'none'}")


def load(df, path):
    df.write.mode("overwrite").parquet(path)
    print(f"Written to {path}")


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("churn-etl").getOrCreate()

    raw = extract(spark, args.input)
    curated = transform(clean(raw))
    quality_report(curated)
    load(curated, args.output)

    spark.stop()


if __name__ == "__main__":
    main()
