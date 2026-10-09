# Customer Churn Prediction

Predicts which telecom customers are likely to leave (churn), so a business can target them with retention offers.

## Dataset
- churn.csv: telecom customer data, 7,043 rows and 21 columns
- Target: Churn (0 = stayed, 1 = left)
- Features include tenure, contract type, monthly charges, payment method and services used

## Method
1. Cleaned the data with pandas
2. Explored it with seaborn and matplotlib (EDA)
3. Encoded categorical features with get_dummies
4. Split the data 80/20 (stratified)
5. Trained and compared Logistic Regression and Random Forest, both with balanced class weights

## Results
| Model | AUC | Churn recall | Churn precision |
|---|---|---|---|
| Logistic Regression | 0.835 | 0.80 | 0.49 |
| Random Forest | 0.821 | 0.66 | 0.56 |

Logistic Regression was chosen as the final model because it catches more of the customers who actually leave.

## Key insights
- Customers in their first 1–2 months churn the most
- Long-tenure customers rarely leave
- (Add 2–3 more from your feature importance and contract charts)

## How to run

pip install pandas seaborn matplotlib scikit-learn jupyter

Open churn.ipynb and run all cells from the top.

## Next steps
SQL analysis, PySpark ETL pipeline, Power BI dashboard, AWS deployment.