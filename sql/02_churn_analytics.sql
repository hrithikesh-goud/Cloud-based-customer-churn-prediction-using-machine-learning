-- Churn analytics in Amazon Athena (database: churn_dw)
-- Run each query in the Athena editor and note the answers in the README.

-- 1. Overall churn rate and revenue lost to churn
SELECT
    COUNT(*)                                              AS customers,
    SUM(churn_flag)                                       AS churned,
    ROUND(100.0 * AVG(churn_flag), 1)                     AS churn_rate_pct,
    ROUND(SUM(CASE WHEN churn_flag = 1 THEN annual_revenue END), 0) AS annual_revenue_lost
FROM churn_dw.customer_features;

-- 2. Churn rate by contract type
SELECT contract,
       COUNT(*)                          AS customers,
       ROUND(100.0 * AVG(churn_flag), 1) AS churn_rate_pct
FROM churn_dw.customer_features
GROUP BY contract
ORDER BY churn_rate_pct DESC;

-- 3. Churn by tenure group: when do customers leave?
SELECT tenure_group,
       COUNT(*)                          AS customers,
       ROUND(100.0 * AVG(churn_flag), 1) AS churn_rate_pct
FROM churn_dw.customer_features
GROUP BY tenure_group
ORDER BY MIN(tenure);

-- 4. Payment method vs churn
SELECT paymentmethod,
       ROUND(100.0 * AVG(churn_flag), 1) AS churn_rate_pct,
       ROUND(AVG(monthlycharges), 2)     AS avg_monthly_charge
FROM churn_dw.customer_features
GROUP BY paymentmethod
ORDER BY churn_rate_pct DESC;

-- 5. Do customers with more services stay longer?
SELECT num_services,
       COUNT(*)                          AS customers,
       ROUND(100.0 * AVG(churn_flag), 1) AS churn_rate_pct
FROM churn_dw.customer_features
GROUP BY num_services
ORDER BY num_services;

-- 6. Highest-risk segments: contract x internet service, ranked (window function)
SELECT contract,
       internetservice,
       customers,
       churn_rate_pct,
       RANK() OVER (ORDER BY churn_rate_pct DESC) AS risk_rank
FROM (
    SELECT contract,
           internetservice,
           COUNT(*)                          AS customers,
           ROUND(100.0 * AVG(churn_flag), 1) AS churn_rate_pct
    FROM churn_dw.customer_features
    GROUP BY contract, internetservice
) AS segments
WHERE customers >= 50
ORDER BY risk_rank;

-- 7. Share of each tenure group's revenue that churned (window function)
SELECT tenure_group,
       ROUND(SUM(annual_revenue), 0) AS total_revenue,
       ROUND(SUM(CASE WHEN churn_flag = 1 THEN annual_revenue ELSE 0 END), 0) AS churned_revenue,
       ROUND(100.0 * SUM(CASE WHEN churn_flag = 1 THEN annual_revenue ELSE 0 END)
             / SUM(SUM(annual_revenue)) OVER (), 1) AS pct_of_all_revenue_lost
FROM churn_dw.customer_features
GROUP BY tenure_group
ORDER BY churned_revenue DESC;

-- 8. Revenue at risk by model risk tier (joins predictions to the warehouse)
SELECT p.risk_tier,
       COUNT(*)                         AS customers,
       ROUND(SUM(p.annual_revenue), 0)  AS annual_revenue_at_risk,
       ROUND(AVG(p.churn_probability), 3) AS avg_churn_probability
FROM churn_dw.churn_predictions p
JOIN churn_dw.customer_features c ON c.customerid = p.customerid
WHERE c.churn_flag = 0              -- current customers only
GROUP BY p.risk_tier
ORDER BY avg_churn_probability DESC;

-- 9. Top 20 current customers to contact first (high risk, high value)
SELECT p.customerid,
       c.contract,
       c.tenure,
       p.monthlycharges,
       p.churn_probability
FROM churn_dw.churn_predictions p
JOIN churn_dw.customer_features c ON c.customerid = p.customerid
WHERE c.churn_flag = 0 AND p.risk_tier = 'High'
ORDER BY p.churn_probability * p.monthlycharges DESC
LIMIT 20;
