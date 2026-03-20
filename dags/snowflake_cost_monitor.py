import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator

# custom modules must be importable inside the container
sys.path.insert(0, "/opt/airflow")

from plugins.snowflake_client import run_query
from notifier.notifier import send_anomaly_alert, send_budget_alert, send_daily_digest

# Constants pulled from environment 
DAILY_BUDGET   = float(os.environ.get("DAILY_BUDGET_CREDITS", 10))
THRESHOLD_PCT  = float(os.environ.get("ANOMALY_THRESHOLD_PCT", 30))

# SQL loader helper 
def _load_sql(filename: str) -> str:
    """Read a SQL file from the mounted sql/ directory."""
    path = f"/opt/airflow/sql/{filename}"
    with open(path) as f:
        return f.read()


# Task functions

def check_anomalies(**context) -> str:
    """
    Runs anomaly_detection.sql and pushes flagged warehouses to XCom.
    Returns the next task_id for the branch operator.
    """
    sql = _load_sql("anomaly_detection.sql")
    # Replace the bind variable :threshold with the actual value
    sql = sql.replace(":threshold", str(THRESHOLD_PCT))

    rows = run_query(sql)
    flagged = [r for r in rows if r.get("PCT_ABOVE_AVG", 0) > THRESHOLD_PCT]

    # Push flagged rows so the alert task can read them
    context["ti"].xcom_push(key="flagged_warehouses", value=flagged)

    if flagged:
        return "send_anomaly_alert"
    return "no_anomaly"


def send_anomaly_alert_task(**context) -> None:
    """Fires a Slack alert for every flagged warehouse."""
    flagged = context["ti"].xcom_pull(
        task_ids="check_anomalies", key="flagged_warehouses"
    )
    for row in flagged:
        send_anomaly_alert(
            warehouse=row["WAREHOUSE_NAME"],
            credits_yesterday=float(row["CREDITS_USED_YESTERDAY"]),
            rolling_avg=float(row["ROLLING_AVG_7D"]),
            pct_above=float(row["PCT_ABOVE_AVG"]),
        )


def check_budget(**context) -> str:
    """
    Runs budget_check.sql and pushes the result to XCom.
    Returns the next task_id for the branch operator.
    """
    sql = _load_sql("budget_check.sql")
    rows = run_query(sql)

    if not rows:
        context["ti"].xcom_push(key="budget_row", value=None)
        return "no_budget_breach"

    row = rows[0]
    context["ti"].xcom_push(key="budget_row", value=row)

    credits_used = float(row.get("CREDITS_USED_YESTERDAY", 0))
    if credits_used > DAILY_BUDGET:
        return "send_budget_alert"
    return "no_budget_breach"


def send_budget_alert_task(**context) -> None:
    """Fires a Slack alert when daily spend exceeds the budget."""
    row = context["ti"].xcom_pull(
        task_ids="check_budget", key="budget_row"
    )
    send_budget_alert(
        credits_used=float(row["CREDITS_USED_YESTERDAY"]),
        budget=DAILY_BUDGET,
        warehouses_active=int(row["WAREHOUSES_ACTIVE"]),
    )


def send_daily_digest_task(**context) -> None:
    """
    Always fires — pulls the cost breakdown and sends the morning digest.
    Runs after both branch paths have converged.
    """
    sql = _load_sql("query_cost_breakdown.sql")
    rows = run_query(sql)

    total_credits = sum(float(r.get("CREDITS_USED", 0)) for r in rows)
    send_daily_digest(rows=rows, total_credits=total_credits)


# DAG definition 

default_args = {
    "owner":            "data-engineering",
    "retries":          1,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="snowflake_cost_monitor",
    description="Daily Snowflake cost anomaly detection and budget alerting",
    schedule="0 8 * * *",         
    start_date=datetime(2024, 1, 1),
    catchup=False,                  # don't backfill missed runs
    default_args=default_args,
    tags=["snowflake", "cost", "monitoring"],
) as dag:

    # Branch 1: Anomaly detection
    t_check_anomalies = BranchPythonOperator(
        task_id="check_anomalies",
        python_callable=check_anomalies,
    )

    t_send_anomaly_alert = PythonOperator(
        task_id="send_anomaly_alert",
        python_callable=send_anomaly_alert_task,
    )

    t_no_anomaly = EmptyOperator(task_id="no_anomaly")

    # Branch 2: Budget check 
    t_check_budget = BranchPythonOperator(
        task_id="check_budget",
        python_callable=check_budget,
    )

    t_send_budget_alert = PythonOperator(
        task_id="send_budget_alert",
        python_callable=send_budget_alert_task,
    )

    t_no_budget_breach = EmptyOperator(task_id="no_budget_breach")

    # Convergence point 
    # trigger_rule="none_failed_min_one_success" means:
    # run as long as at least one upstream task succeeded and none failed.
    # This lets the digest fire whether or not alerts were triggered.
    t_daily_digest = PythonOperator(
        task_id="send_daily_digest",
        python_callable=send_daily_digest_task,
        trigger_rule="none_failed_min_one_success",
    )

    # Wiring up the tasks
    t_check_anomalies >> [t_send_anomaly_alert, t_no_anomaly]
    t_check_budget    >> [t_send_budget_alert,  t_no_budget_breach]

    [t_send_anomaly_alert, t_no_anomaly,
     t_send_budget_alert,  t_no_budget_breach] >> t_daily_digest