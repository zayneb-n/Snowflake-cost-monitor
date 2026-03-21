# Quick script to preview all three Slack message types with fake data


import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from notifier.notifier import send_anomaly_alert, send_budget_alert, send_daily_digest

print("Sending anomaly alert... 🚨")
send_anomaly_alert(
    warehouse="COMPUTE_WH",
    credits_yesterday=14.5,
    rolling_avg=8.2,
    pct_above=76.8,
)
print("Done.")

print("Sending budget alert... 💸")
send_budget_alert(
    credits_used=13.4,
    budget=10.0,
    warehouses_active=2,
)
print("Done.")

print("Sending daily digest... 📊")
send_daily_digest(
    rows=[
        {"WAREHOUSE_NAME": "COMPUTE_WH",  "CREDITS_USED": 9.2,
         "ESTIMATED_USD": 27.6, "JOB_COUNT": 54},
        {"WAREHOUSE_NAME": "LOAD_WH",     "CREDITS_USED": 3.1,
         "ESTIMATED_USD": 9.3,  "JOB_COUNT": 12},
        {"WAREHOUSE_NAME": "ANALYTICS_WH","CREDITS_USED": 1.1,
         "ESTIMATED_USD": 3.3,  "JOB_COUNT": 7},
    ],
    total_credits=13.4,
)
print("Done.")

print("\n All three messages sent. Check your Slack channel.")