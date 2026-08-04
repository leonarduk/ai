# Octopus Agile free-electricity alert

This zero-dependency Python job checks tomorrow's half-hourly Octopus Agile prices and sends a webhook when any inclusive-of-VAT rate is at or below a configurable threshold.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OCTOPUS_PRODUCT_CODE` | `AGILE-24-10-01` | Agile product code |
| `OCTOPUS_REGION` | `C` | GSP/region suffix used to derive the tariff code |
| `OCTOPUS_TARIFF_CODE` | `E-1R-<product>-<region>` | Optional full tariff-code override |
| `ALERT_WEBHOOK_URL` | none | Slack-compatible incoming webhook URL |
| `ALERT_THRESHOLD_PENCE` | `0` | Alert threshold in pence/kWh (use `5` for very-cheap alerts) |
| `ALERT_TIMEZONE` | `Europe/London` | Timezone used to define and display tomorrow |

Run a read-only check locally:

```bash
python projects/06-octopus-agile-alert/agile_alert.py --dry-run
```

The included GitHub Actions workflow runs daily at 16:30 UTC, after the usual publication time, and can also be dispatched manually. Add an `ALERT_WEBHOOK_URL` repository secret and, if required, repository variables for the other settings. When no qualifying slot exists, the job remains silent apart from its action log. API or webhook failures make the job fail rather than silently losing an alert.

The webhook body is `{"text": "..."}`, which works directly with Slack incoming webhooks and can be adapted by a generic webhook relay for email or push notifications.
