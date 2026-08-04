"""Fetch tomorrow's Octopus Agile prices and alert on free-energy slots."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

API_ROOT = "https://api.octopus.energy/v1"


@dataclass(frozen=True)
class Config:
    product_code: str
    tariff_code: str
    webhook_url: str | None = None
    threshold: float = 0.0
    timezone: str = "Europe/London"

    @classmethod
    def from_environment(cls) -> "Config":
        # GitHub Actions expands unset repository variables to empty strings,
        # so use ``or`` rather than only getenv's default argument.
        product = os.getenv("OCTOPUS_PRODUCT_CODE") or "AGILE-24-10-01"
        region = (os.getenv("OCTOPUS_REGION") or "C").strip().upper()
        tariff = os.getenv("OCTOPUS_TARIFF_CODE") or f"E-1R-{product}-{region}"
        return cls(
            product_code=product,
            tariff_code=tariff,
            webhook_url=os.getenv("ALERT_WEBHOOK_URL"),
            threshold=float(os.getenv("ALERT_THRESHOLD_PENCE") or "0"),
            timezone=os.getenv("ALERT_TIMEZONE") or "Europe/London",
        )


def tomorrow_period(now: datetime, timezone: str) -> tuple[datetime, datetime, date]:
    """Return UTC API boundaries for tomorrow in the configured local timezone."""
    zone = ZoneInfo(timezone)
    local_tomorrow = now.astimezone(zone).date() + timedelta(days=1)
    start = datetime.combine(local_tomorrow, time.min, zone).astimezone(UTC)
    end = datetime.combine(
        local_tomorrow + timedelta(days=1), time.min, zone
    ).astimezone(UTC)
    return start, end, local_tomorrow


def rates_url(config: Config, start: datetime, end: datetime) -> str:
    product = urllib.parse.quote(config.product_code, safe="")
    tariff = urllib.parse.quote(config.tariff_code, safe="")
    query = urllib.parse.urlencode(
        {
            "period_from": start.isoformat().replace("+00:00", "Z"),
            "period_to": end.isoformat().replace("+00:00", "Z"),
            "page_size": 100,
        }
    )
    return f"{API_ROOT}/products/{product}/electricity-tariffs/{tariff}/standard-unit-rates/?{query}"


def fetch_rates(
    url: str, opener: Callable[..., Any] = urllib.request.urlopen
) -> list[dict[str, Any]]:
    """Fetch every page from an Octopus rates response."""
    results: list[dict[str, Any]] = []
    while url:
        request = urllib.request.Request(
            url, headers={"User-Agent": "ai-systems-lab-agile-alert/1.0"}
        )
        with opener(request, timeout=20) as response:
            payload = json.load(response)
        if not isinstance(payload.get("results"), list):
            raise ValueError("Octopus response did not contain a results list")
        results.extend(payload["results"])
        url = payload.get("next")
    return results


def cheap_slots(rates: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    return sorted(
        (rate for rate in rates if float(rate["value_inc_vat"]) <= threshold),
        key=lambda rate: rate["valid_from"],
    )


def build_message(
    slots: list[dict[str, Any]], day: date, timezone: str, threshold: float
) -> str:
    zone = ZoneInfo(timezone)
    lines = [
        f"Octopus Agile alert for {day.isoformat()}: {len(slots)} slot(s) at or below {threshold:g}p/kWh"
    ]
    for slot in slots:
        start = datetime.fromisoformat(
            slot["valid_from"].replace("Z", "+00:00")
        ).astimezone(zone)
        end = datetime.fromisoformat(
            slot["valid_to"].replace("Z", "+00:00")
        ).astimezone(zone)
        lines.append(
            f"- {start:%H:%M}–{end:%H:%M}: {float(slot['value_inc_vat']):g}p/kWh"
        )
    return "\n".join(lines)


def send_webhook(
    url: str, message: str, opener: Callable[..., Any] = urllib.request.urlopen
) -> None:
    """POST a broadly compatible JSON message (Slack uses ``text``)."""
    request = urllib.request.Request(
        url,
        data=json.dumps({"text": message}).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ai-systems-lab-agile-alert/1.0",
        },
        method="POST",
    )
    with opener(request, timeout=20) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Webhook returned HTTP {response.status}")


def run(config: Config, now: datetime | None = None) -> int:
    start, end, day = tomorrow_period(now or datetime.now(UTC), config.timezone)
    slots = cheap_slots(fetch_rates(rates_url(config, start, end)), config.threshold)
    if not slots:
        print(f"No Octopus Agile slots at or below {config.threshold:g}p/kWh on {day}.")
        return 0

    message = build_message(slots, day, config.timezone, config.threshold)
    print(message)
    if not config.webhook_url:
        print(
            "ERROR: qualifying slots found but ALERT_WEBHOOK_URL is not configured.",
            file=sys.stderr,
        )
        return 2
    send_webhook(config.webhook_url, message)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print qualifying rates without sending a webhook",
    )
    args = parser.parse_args()
    try:
        config = Config.from_environment()
        if args.dry_run:
            # A dry run intentionally treats a missing webhook as success.
            start, end, day = tomorrow_period(datetime.now(UTC), config.timezone)
            slots = cheap_slots(
                fetch_rates(rates_url(config, start, end)), config.threshold
            )
            print(
                build_message(slots, day, config.timezone, config.threshold)
                if slots
                else f"No qualifying slots on {day}."
            )
            return 0
        return run(config)
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        KeyError,
        RuntimeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
