import importlib.util
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "agile_alert", Path(__file__).with_name("agile_alert.py")
)
agile_alert = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = agile_alert
SPEC.loader.exec_module(agile_alert)


class Response:
    def __init__(self, payload=None, status=200):
        self.payload = payload or {}
        self.status = status

    def read(self, *_args):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class AgileAlertTests(unittest.TestCase):
    def test_tomorrow_period_observes_british_summer_time(self):
        start, end, day = agile_alert.tomorrow_period(
            datetime(2026, 7, 29, 16, tzinfo=UTC), "Europe/London"
        )
        self.assertEqual(day.isoformat(), "2026-07-30")
        self.assertEqual(start.isoformat(), "2026-07-29T23:00:00+00:00")
        self.assertEqual(end.isoformat(), "2026-07-30T23:00:00+00:00")

    def test_fetch_rates_follows_pagination(self):
        responses = iter(
            [
                Response(
                    {"results": [{"id": 1}], "next": "https://example.test/page-2"}
                ),
                Response({"results": [{"id": 2}], "next": None}),
            ]
        )
        self.assertEqual(
            agile_alert.fetch_rates(
                "https://example.test/page-1", lambda *_args, **_kwargs: next(responses)
            ),
            [{"id": 1}, {"id": 2}],
        )

    def test_detects_zero_and_negative_slots(self):
        rates = [
            {"value_inc_vat": 2, "valid_from": "2026-07-30T00:00:00Z"},
            {"value_inc_vat": 0, "valid_from": "2026-07-30T00:30:00Z"},
            {"value_inc_vat": -1.2, "valid_from": "2026-07-30T01:00:00Z"},
        ]
        self.assertEqual(
            [r["value_inc_vat"] for r in agile_alert.cheap_slots(rates, 0)], [0, -1.2]
        )

    def test_webhook_posts_slack_compatible_payload(self):
        captured = {}

        def open_request(request, **_kwargs):
            captured["body"] = json.loads(request.data)
            return Response(status=204)

        agile_alert.send_webhook("https://example.test/hook", "hello", open_request)
        self.assertEqual(captured["body"], {"text": "hello"})


if __name__ == "__main__":
    unittest.main()
