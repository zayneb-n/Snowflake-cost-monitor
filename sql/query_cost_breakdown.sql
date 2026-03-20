-- Cost Breakdown: warehouse-by-warehouse digest for yesterday
-- Used by the DAG for the daily digest message AND manually after alerts.

SELECT
    WAREHOUSE_NAME,
    ROUND(SUM(CREDITS_USED), 4)             AS credits_used,
    ROUND(SUM(CREDITS_USED) * 3.0, 2)       AS estimated_usd,   -- $3/credit on-demand
    COUNT(*)                                AS job_count,
    ROUND(AVG(CREDITS_USED), 6)             AS avg_credits_per_job

FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE
    START_TIME >= DATEADD('day', -1, CURRENT_DATE)
    AND START_TIME  < CURRENT_DATE
    AND WAREHOUSE_NAME IS NOT NULL

GROUP BY 1
ORDER BY credits_used DESC;