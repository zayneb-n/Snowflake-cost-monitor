-- Anomaly Detection: flag warehouses spending 30%+ above their 7-day rolling average
-- Runs against yesterday's data. ACCOUNT_USAGE has ~1hr latency, so we run at 08:00 UTC.

WITH daily_usage AS (
    SELECT
        WAREHOUSE_NAME,
        DATE_TRUNC('day', START_TIME)        AS usage_date,
        SUM(CREDITS_USED)                    AS daily_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE
        START_TIME >= DATEADD('day', -8, CURRENT_DATE)  -- 7 days history + yesterday
        AND START_TIME  < CURRENT_DATE                   -- exclude today (incomplete)
        AND WAREHOUSE_NAME IS NOT NULL
    GROUP BY 1, 2
),

rolling_stats AS (
    SELECT
        WAREHOUSE_NAME,
        usage_date,
        daily_credits,

        -- 7-day rolling average EXCLUDING the current day
        AVG(daily_credits) OVER (
            PARTITION BY WAREHOUSE_NAME
            ORDER BY usage_date
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS rolling_avg_7d,

        -- 7-day rolling standard deviation for context
        STDDEV(daily_credits) OVER (
            PARTITION BY WAREHOUSE_NAME
            ORDER BY usage_date
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS rolling_stddev_7d

    FROM daily_usage
)

SELECT
    WAREHOUSE_NAME,
    usage_date,
    ROUND(daily_credits, 4)                                      AS credits_used_yesterday,
    ROUND(rolling_avg_7d, 4)                                     AS rolling_avg_7d,
    ROUND(rolling_stddev_7d, 4)                                  AS rolling_stddev_7d,
    ROUND((daily_credits - rolling_avg_7d) / NULLIF(rolling_avg_7d, 0) * 100, 2)
                                                                 AS pct_above_avg

FROM rolling_stats
WHERE
    usage_date = DATEADD('day', -1, CURRENT_DATE)           -- yesterday only
    AND rolling_avg_7d IS NOT NULL                          -- need history to compare
    AND daily_credits > rolling_avg_7d * (1 + :threshold / 100.0)  -- :threshold = 30
ORDER BY pct_above_avg DESC;