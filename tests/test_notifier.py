import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Make slack/ importable when running pytest from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slack.notifier import (
    send_anomaly_alert,
    send_budget_alert,
    send_daily_digest,
    _send,
)


# Helpers 

FAKE_WEBHOOK = "https://hooks.slack.com/services/FAKE/FAKE/fake123"


def _set_webhook(monkeypatch_or_env: str = FAKE_WEBHOOK):
    """Set the webhook env var so _send() doesn't raise Environment Error"""
    os.environ["SLACK_WEBHOOK_URL"] = monkeypatch_or_env


def _get_sent_payload(mock_urlopen) -> dict:
    """Extract and parse the JSON payload that was sent to the mock"""
    call_args = mock_urlopen.call_args
    request_obj = call_args[0][0]          # first positional arg = Request object
    return json.loads(request_obj.data.decode("utf-8"))


# _send() unit tests 

class TestSendCore(unittest.TestCase):

    def test_raises_when_webhook_missing(self):
        """_send() must raise EnvironmentError if webhook URL is not set."""
        os.environ.pop("SLACK_WEBHOOK_URL", None)
        with self.assertRaises(EnvironmentError):
            _send({"text": "hello"})

    @patch("urllib.request.urlopen")
    def test_sends_correct_content_type(self, mock_urlopen):
        """Request must have Content-Type: application/json."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        _send({"blocks": []})

        request_obj = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request_obj.get_header("Content-type"), "application/json"
        )

    @patch("urllib.request.urlopen")
    def test_raises_on_non_200_response(self, mock_urlopen):
        """_send() must raise RuntimeError if Slack returns non-200."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with self.assertRaises(RuntimeError):
            _send({"blocks": []})


# Send_anomaly_alert() tests

class TestAnomalyAlert(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_payload_contains_warehouse_name(self, mock_urlopen):
        """Anomaly alert payload must reference the warehouse name."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        send_anomaly_alert(
            warehouse="COMPUTE_WH",
            credits_yesterday=14.5,
            rolling_avg=8.2,
            pct_above=76.8,
        )

        payload = _get_sent_payload(mock_urlopen)
        payload_str = json.dumps(payload)
        self.assertIn("COMPUTE_WH", payload_str)

    @patch("urllib.request.urlopen")
    def test_payload_contains_pct_above(self, mock_urlopen):
        """Anomaly alert must mention the percentage spike."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        send_anomaly_alert(
            warehouse="COMPUTE_WH",
            credits_yesterday=14.5,
            rolling_avg=8.2,
            pct_above=76.8,
        )

        payload = _get_sent_payload(mock_urlopen)
        payload_str = json.dumps(payload)
        self.assertIn("76.8", payload_str)

    @patch("urllib.request.urlopen")
    def test_anomaly_alert_calls_urlopen_once(self, mock_urlopen):
        """One warehouse = exactly one HTTP call to Slack."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        send_anomaly_alert("COMPUTE_WH", 14.5, 8.2, 76.8)

        mock_urlopen.assert_called_once()


# Send_budget_alert() tests

class TestBudgetAlert(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_payload_contains_overage(self, mock_urlopen):
        """Budget alert must include the overage amount."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        send_budget_alert(
            credits_used=13.4,
            budget=10.0,
            warehouses_active=2,
        )

        payload = _get_sent_payload(mock_urlopen)
        payload_str = json.dumps(payload)
        # overage = 13.4 - 10.0 = 3.4 credits
        self.assertIn("3.4", payload_str)

    @patch("urllib.request.urlopen")
    def test_payload_contains_usd_estimate(self, mock_urlopen):
        """Budget alert must include a USD estimate."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        send_budget_alert(credits_used=13.4, budget=10.0, warehouses_active=2)

        payload = _get_sent_payload(mock_urlopen)
        payload_str = json.dumps(payload)
        # overage 3.4 * $3 = $10.2
        self.assertIn("10.2", payload_str)


# Send_daily_digest() tests 

class TestDailyDigest(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_digest_shows_warehouse_name(self, mock_urlopen):
        """Daily digest must list each warehouse."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        rows = [
            {"WAREHOUSE_NAME": "COMPUTE_WH", "CREDITS_USED": 4.2,
             "ESTIMATED_USD": 12.6, "JOB_COUNT": 38},
        ]
        send_daily_digest(rows=rows, total_credits=4.2)

        payload = _get_sent_payload(mock_urlopen)
        payload_str = json.dumps(payload)
        self.assertIn("COMPUTE_WH", payload_str)

    @patch("urllib.request.urlopen")
    def test_digest_handles_empty_rows(self, mock_urlopen):
        """Digest must not crash when there was no activity yesterday."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Should not raise
        send_daily_digest(rows=[], total_credits=0.0)
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_digest_total_credits_in_payload(self, mock_urlopen):
        """Digest must display the correct total credits."""
        _set_webhook()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        rows = [
            {"WAREHOUSE_NAME": "COMPUTE_WH", "CREDITS_USED": 4.2,
             "ESTIMATED_USD": 12.6, "JOB_COUNT": 38},
            {"WAREHOUSE_NAME": "LOAD_WH", "CREDITS_USED": 2.1,
             "ESTIMATED_USD": 6.3, "JOB_COUNT": 12},
        ]
        send_daily_digest(rows=rows, total_credits=6.3)

        payload = _get_sent_payload(mock_urlopen)
        payload_str = json.dumps(payload)
        self.assertIn("6.3", payload_str)


if __name__ == "__main__":
    unittest.main()