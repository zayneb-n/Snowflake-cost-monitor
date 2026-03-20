import os
import snowflake.connector
from contextlib import contextmanager


def get_connection_params() -> dict:
    params = {
        "account":   os.environ["SNOWFLAKE_ACCOUNT"],
        "user":      os.environ["SNOWFLAKE_USER"],
        "password":  os.environ["SNOWFLAKE_PASSWORD"],
        "role":      os.environ["SNOWFLAKE_ROLE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database":  os.environ["SNOWFLAKE_DATABASE"],
        "schema":    "ACCOUNT_USAGE",
    }
    # Validate nothing is empty
    missing = [k for k, v in params.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing Snowflake env vars: {missing}")
    return params


@contextmanager
def get_snowflake_connection():
    """
    Context manager that opens a Snowflake connection and guarantees
    it closes cleanly even if an exception is raised mid-query.

    Usage:
        with get_snowflake_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
    """
    conn = None
    try:
        conn = snowflake.connector.connect(**get_connection_params())
        yield conn
    finally:
        if conn:
            conn.close()


def run_query(sql: str) -> list[dict]:
    """
    Execute a SQL string and return results as a list of dicts.
    Each dict maps column_name → value for one row.

    Usage:
        rows = run_query("SELECT WAREHOUSE_NAME, SUM(CREDITS_USED) ...")
        for row in rows:
            print(row["WAREHOUSE_NAME"], row["CREDITS_USED"])
    """
    with get_snowflake_connection() as conn:
        cursor = conn.cursor(snowflake.connector.DictCursor)
        try:
            cursor.execute(sql)
            return cursor.fetchall()
        finally:
            cursor.close()