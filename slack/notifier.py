import os
import json
import urllib.request
from datetime import date


def _send(payload: dict) -> None:
    """
    Core HTTP sender. Uses stdlib urllib — no requests library needed.
    Raises clearly if the webhook URL is missing or Slack rejects the message.
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise EnvironmentError("SLACK_WEBHOOK_URL environment variable is not set.")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        if response.status != 200:
            raise RuntimeError(f"Slack returned HTTP {response.status}")


def send_anomaly_alert(warehouse: str, credits_yesterday: float,
                       rolling_avg: float, pct_above: float) -> None:
    """
         Fires when a warehouse is 30%+ above its 7-day rolling average.
    """
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Snowflake Cost Anomaly Detected"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Warehouse*\n{warehouse}"},
                    {"type": "mrkdwn", "text": f"*Date*\n{date.today()}"},
                    {"type": "mrkdwn", "text": f"*Credits Yesterday*\n{credits_yesterday:.2f}"},
                    {"type": "mrkdwn", "text": f"*7-Day Average*\n{rolling_avg:.2f}"},
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":rotating_light: *{pct_above:.1f}% above normal* — "
                        f"this warehouse spent *{credits_yesterday - rolling_avg:.2f} "
                        f"extra credits* yesterday compared to its 7-day average.\n"
                        f"Check `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY` for details."
                    )
                }
            },
            {"type": "divider"}
        ]
    }
    _send(payload)


def send_budget_alert(credits_used: float, budget: float,
                      warehouses_active: int) -> None:
    """
    Fires when total daily spend exceeds the configured credit budget.
    """
    overage = credits_used - budget
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Snowflake Daily Budget Exceeded"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Date*\n{date.today()}"},
                    {"type": "mrkdwn", "text": f"*Warehouses Active*\n{warehouses_active}"},
                    {"type": "mrkdwn", "text": f"*Credits Used*\n{credits_used:.2f}"},
                    {"type": "mrkdwn", "text": f"*Daily Budget*\n{budget:.2f}"},
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":money_with_wings: You are *{overage:.2f} credits over budget* "
                        f"(~${overage * 3:.2f} USD at $3/credit).\n"
                        f"Review active warehouses and consider suspending idle ones."
                    )
                }
            },
            {"type": "divider"}
        ]
    }
    _send(payload)


def send_daily_digest(rows: list[dict], total_credits: float) -> None:
    """
    Fires every morning regardless — the cost summary for yesterday.
    rows: output of query_cost_breakdown.sql, list of dicts with keys:
          WAREHOUSE_NAME, CREDITS_USED, ESTIMATED_USD, JOB_COUNT
    """
    # Build one line per warehouse
    breakdown_lines = "\n".join([
        f"• *{r['WAREHOUSE_NAME']}* — "
        f"`{r['CREDITS_USED']:.2f}` credits "
        f"(~${r['ESTIMATED_USD']:.2f}) "
        f"across {r['JOB_COUNT']} jobs"
        for r in rows
    ])

    if not breakdown_lines:
        breakdown_lines = "_No warehouse activity yesterday._"

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Snowflake Daily Cost Digest"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Date:* {date.today()}    |    *Total:* `{total_credits:.2f}` credits (~${total_credits * 3:.2f} USD)"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Breakdown by warehouse:*\n{breakdown_lines}"
                }
            },
            {"type": "divider"}
        ]
    }
    _send(payload)