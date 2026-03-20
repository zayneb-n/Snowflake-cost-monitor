-- Budget Guard: check if yesterday's total spend exceeded the daily credit budget
-- Returns one row. The DAG checks if credits_used_yesterday > budget threshold.

SELECT
    DATE_TRUNC('day', START_TIME)           AS usage_date,
    ROUND(SUM(CREDITS_USED), 4)             AS credits_used_yesterday,
    COUNT(DISTINCT WAREHOUSE_NAME)          AS warehouses_active

FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE
    START_TIME >= DATEADD('day', -1, CURRENT_DATE)
    AND START_TIME  < CURRENT_DATE
    AND WAREHOUSE_NAME IS NOT NULL

GROUP BY 1
ORDER BY 1 DESC
LIMIT 1;