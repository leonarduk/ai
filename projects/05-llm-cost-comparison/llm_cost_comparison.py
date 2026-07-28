#!/usr/bin/env python3
"""Interactive LLM cost comparison: local inference vs. hosted APIs.

Walks the user through a series of prompts to estimate the effective cost of
running an LLM locally (owned hardware or rented cloud GPU) and compares it
against hosted providers (DeepSeek, Claude) using pricing stored in
``pricing.json``.

Design goals:
  * Zero required third-party dependencies (stdlib only) so it runs on a
    plain Windows Python install with no ``pip install`` step.
  * All cost math lives in small, pure, unit-testable functions. The
    interactive layer is a thin wrapper around them so the logic can be
    exercised in tests without mocking ``input()``.
  * Best-effort Windows/NVIDIA GPU detection via ``nvidia-smi`` and an
    optional local-endpoint throughput benchmark (Ollama or an
    OpenAI-compatible ``/v1/chat/completions`` server). Both degrade
    gracefully to manual input if unavailable.

Usage:
    python llm_cost_comparison.py                # interactive
    python llm_cost_comparison.py --non-interactive --config example.json
    python llm_cost_comparison.py --export json --export-path out.json
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

DEFAULT_PRICING_PATH = Path(__file__).parent / "pricing.json"
DAYS_PER_MONTH = 30
HOURS_PER_MONTH = DAYS_PER_MONTH * 24


class ConfigError(ValueError):
    """Raised for a malformed --non-interactive config, or an unknown preset key.

    Deliberately distinct from a bare ``KeyError``/``TypeError`` traceback:
    this is user-facing config, so a missing or misspelled field should say
    exactly what's missing rather than dumping a Python stack trace.
    """


# --------------------------------------------------------------------------
# Pricing
# --------------------------------------------------------------------------


def load_pricing(path: Path = DEFAULT_PRICING_PATH) -> dict:
    """Load hosted-provider pricing from a JSON config file.

    Kept in its own function (rather than inlined literals) so pricing can
    be updated by editing ``pricing.json`` without touching this script.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_models(pricing: dict):
    """Yield (provider_key, model_key, model_info) for every priced model."""
    for provider_key, provider in pricing.get("providers", {}).items():
        for model_key, model_info in provider.get("models", {}).items():
            yield provider_key, model_key, model_info


# --------------------------------------------------------------------------
# Workload
# --------------------------------------------------------------------------


@dataclass
class Workload:
    """Describes the traffic the comparison should be sized against."""

    requests_per_day: float
    avg_input_tokens: float
    avg_output_tokens: float

    @property
    def monthly_input_tokens(self) -> float:
        return self.requests_per_day * self.avg_input_tokens * DAYS_PER_MONTH

    @property
    def monthly_output_tokens(self) -> float:
        return self.requests_per_day * self.avg_output_tokens * DAYS_PER_MONTH

    @property
    def monthly_total_tokens(self) -> float:
        return self.monthly_input_tokens + self.monthly_output_tokens


@dataclass(frozen=True)
class WorkloadPreset:
    """A named, plain-language traffic scenario.

    Guessing "requests per day" and "average input tokens" cold is a bad
    starting point for someone who has never measured their own usage.
    Presets give a menu of scenarios described in terms people actually
    reason in ("a live app serving many users"), with the underlying numbers
    filled in — while still leaving room for a fully custom entry.
    """

    key: str
    label: str
    description: str
    requests_per_day: float
    avg_input_tokens: float
    avg_output_tokens: float

    def to_workload(self) -> Workload:
        return Workload(
            self.requests_per_day, self.avg_input_tokens, self.avg_output_tokens
        )


WORKLOAD_PRESETS: tuple = (
    WorkloadPreset(
        key="casual",
        label="Casual personal use",
        description=(
            "A handful of questions a day, similar to using it instead of a search engine."
        ),
        requests_per_day=20,
        avg_input_tokens=300,
        avg_output_tokens=250,
    ),
    WorkloadPreset(
        key="daily_assistant",
        label="Daily work assistant",
        description=(
            "Used on and off throughout the workday for drafting, research, and quick "
            "coding help."
        ),
        requests_per_day=150,
        avg_input_tokens=800,
        avg_output_tokens=500,
    ),
    WorkloadPreset(
        key="coding_agent",
        label="Autonomous coding agent",
        description=(
            "An agent that reads files and runs commands on its own (like an AI coding "
            "assistant). Each turn re-sends a lot of file/context content, so input "
            "tokens are large relative to output."
        ),
        requests_per_day=500,
        avg_input_tokens=4000,
        avg_output_tokens=800,
    ),
    WorkloadPreset(
        key="team_tool",
        label="Small team internal tool",
        description="A shared assistant used by a small team (roughly 5-20 people) all day.",
        requests_per_day=2000,
        avg_input_tokens=600,
        avg_output_tokens=400,
    ),
    WorkloadPreset(
        key="production_app",
        label="Production customer-facing app",
        description="A live app serving many users' requests around the clock.",
        requests_per_day=50000,
        avg_input_tokens=500,
        avg_output_tokens=300,
    ),
)


def get_preset(key: str) -> WorkloadPreset:
    """Look up a preset by key, raising ``ConfigError`` with valid keys listed."""
    for preset in WORKLOAD_PRESETS:
        if preset.key == key:
            return preset
    valid = ", ".join(p.key for p in WORKLOAD_PRESETS)
    raise ConfigError(f"unknown workload preset {key!r}; valid presets: {valid}")


# --------------------------------------------------------------------------
# Core cost math (pure functions — unit test these directly)
# --------------------------------------------------------------------------


def hosted_monthly_cost(
    workload: Workload, input_per_million: float, output_per_million: float
) -> float:
    """Monthly cost for a hosted API at the given per-million-token rates."""
    return (
        workload.monthly_input_tokens / 1_000_000 * input_per_million
        + workload.monthly_output_tokens / 1_000_000 * output_per_million
    )


def hours_needed_for_workload(
    total_monthly_tokens: float, tokens_per_sec: float
) -> float:
    """Compute-hours per month required to generate the workload's tokens.

    Assumes the local/rented GPU only needs to run while actively producing
    tokens for this workload (i.e. it can idle/power down otherwise). This is
    the right basis for a rented cloud GPU, and the variable-cost basis for
    owned hardware (see ``local_monthly_cost_owned``).
    """
    if tokens_per_sec <= 0:
        raise ValueError("tokens_per_sec must be > 0")
    tokens_per_hour = tokens_per_sec * 3600
    return total_monthly_tokens / tokens_per_hour


def local_monthly_cost_owned(
    hardware_cost: float,
    lifetime_years: float,
    power_watts: float,
    electricity_rate_per_kwh: float,
    hours_needed_per_month: float,
) -> float:
    """Monthly cost for owned local hardware.

    Splits into two components, which matters because they behave
    differently:
      * Hardware amortization is a *fixed* monthly cost — the card ages and
        eventually needs replacing whether it's busy or idle.
      * Electricity is a *variable* cost that only accrues while it's
        actually generating tokens for this workload.
    """
    if lifetime_years <= 0:
        raise ValueError("lifetime_years must be > 0")
    lifetime_months = lifetime_years * 12
    hardware_monthly = hardware_cost / lifetime_months
    power_kw = power_watts / 1000
    variable_monthly = power_kw * electricity_rate_per_kwh * hours_needed_per_month
    return hardware_monthly + variable_monthly


def local_monthly_cost_rented(
    hourly_rate: float, hours_needed_per_month: float
) -> float:
    """Monthly cost for a rented cloud GPU billed per hour of usage."""
    return hourly_rate * hours_needed_per_month


def local_monthly_cost_existing_hardware(
    power_watts: float, electricity_rate_per_kwh: float, hours_needed_per_month: float
) -> float:
    """Monthly cost when the PC/GPU is already owned for other reasons.

    No hardware amortization at all — unlike ``local_monthly_cost_owned``,
    this assumes the machine exists (and its cost is sunk) regardless of
    whether it's ever used for a local LLM. The only cost attributable to
    that use is the extra electricity consumed while it runs. ``power_watts``
    should reflect whichever basis applies:
      * If the machine is already on for other reasons, use the *extra*
        draw the GPU/CPU pull under load, above idle.
      * If it's only powered on to run the local LLM, use the *whole
        system's* draw while running (GPU plus CPU, RAM, storage, etc.) —
        the entire session's electricity is attributable to this use.
    """
    power_kw = power_watts / 1000
    return power_kw * electricity_rate_per_kwh * hours_needed_per_month


def cost_per_million_tokens(monthly_cost: float, monthly_total_tokens: float) -> float:
    """Blended $/1M tokens (input+output combined) for a given monthly cost.

    Blending input and output into one number makes local and hosted costs
    directly comparable even though hosted providers price them separately.
    """
    if monthly_total_tokens <= 0:
        raise ValueError("monthly_total_tokens must be > 0")
    return monthly_cost / monthly_total_tokens * 1_000_000


# --------------------------------------------------------------------------
# Comparison rows / rendering
# --------------------------------------------------------------------------


@dataclass
class ComparisonRow:
    name: str
    monthly_cost: float
    cost_per_million_tokens: float
    notes: str = ""


def build_local_row(
    workload: Workload,
    tokens_per_sec: float,
    mode: str,
    *,
    hardware_cost: float = 0.0,
    lifetime_years: float = 0.0,
    power_watts: float = 0.0,
    electricity_rate_per_kwh: float = 0.0,
    hourly_rate: float = 0.0,
    name: Optional[str] = None,
) -> ComparisonRow:
    hours_needed = hours_needed_for_workload(
        workload.monthly_total_tokens, tokens_per_sec
    )
    if mode == "own":
        monthly_cost = local_monthly_cost_owned(
            hardware_cost,
            lifetime_years,
            power_watts,
            electricity_rate_per_kwh,
            hours_needed,
        )
        name = name or "Local (buying new hardware)"
    elif mode == "existing":
        monthly_cost = local_monthly_cost_existing_hardware(
            power_watts, electricity_rate_per_kwh, hours_needed
        )
        name = name or "Local (electricity only — hardware already owned)"
    elif mode == "rent":
        monthly_cost = local_monthly_cost_rented(hourly_rate, hours_needed)
        name = "Local (rented cloud GPU)"
    else:
        raise ValueError(f"Unknown local cost mode: {mode!r}")
    per_million = cost_per_million_tokens(monthly_cost, workload.monthly_total_tokens)
    notes = f"~{hours_needed:.1f} compute-hrs/month at {tokens_per_sec:.1f} tok/s"
    return ComparisonRow(name, monthly_cost, per_million, notes)


def build_hosted_rows(
    workload: Workload, pricing: dict, selected: Optional[set] = None
) -> list:
    """Build a ComparisonRow for each hosted model in ``pricing``.

    ``selected`` is an optional set of ``"provider/model"`` keys to restrict
    the comparison to; if None, every model in the pricing file is included.
    """
    rows = []
    for provider_key, model_key, model_info in iter_models(pricing):
        full_key = f"{provider_key}/{model_key}"
        if selected is not None and full_key not in selected:
            continue
        for field in ("input_per_million", "output_per_million"):
            if not isinstance(model_info.get(field), (int, float)):
                raise ConfigError(
                    f"pricing model {full_key!r} is missing a numeric {field}"
                )
        monthly_cost = hosted_monthly_cost(
            workload, model_info["input_per_million"], model_info["output_per_million"]
        )
        per_million = cost_per_million_tokens(
            monthly_cost, workload.monthly_total_tokens
        )
        display = model_info.get("display_name", full_key)
        rows.append(ComparisonRow(display, monthly_cost, per_million))
    return rows


def render_table(rows: list) -> str:
    """Render comparison rows as a plain-text table, cheapest first."""
    if not rows:
        return "(no rows to display)"
    rows_sorted = sorted(rows, key=lambda r: r.monthly_cost)
    name_w = max(len("Option"), max(len(r.name) for r in rows_sorted))
    cost_w = max(
        len("Monthly cost"), max(len(f"${r.monthly_cost:,.2f}") for r in rows_sorted)
    )
    per_m_w = max(
        len("$/1M tokens"),
        max(len(f"${r.cost_per_million_tokens:,.2f}") for r in rows_sorted),
    )
    header = f"{'Option':<{name_w}}  {'Monthly cost':>{cost_w}}  {'$/1M tokens':>{per_m_w}}  Notes"
    lines = [header, "-" * len(header)]
    for r in rows_sorted:
        cost_s = f"${r.monthly_cost:,.2f}"
        per_m_s = f"${r.cost_per_million_tokens:,.2f}"
        lines.append(
            f"{r.name:<{name_w}}  {cost_s:>{cost_w}}  {per_m_s:>{per_m_w}}  {r.notes}"
        )
    cheapest = rows_sorted[0]
    most_expensive = rows_sorted[-1]
    if (
        len(rows_sorted) > 1
        and most_expensive.monthly_cost > 0
        and cheapest.monthly_cost > 0
    ):
        multiple = most_expensive.monthly_cost / cheapest.monthly_cost
        lines.append("")
        lines.append(
            f"Cheapest: {cheapest.name} — most expensive option is {multiple:.1f}x its cost."
        )
    return "\n".join(lines)


def export_csv(rows: list, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["option", "monthly_cost_usd", "cost_per_million_tokens_usd", "notes"]
        )
        for r in sorted(rows, key=lambda r: r.monthly_cost):
            writer.writerow(
                [
                    r.name,
                    f"{r.monthly_cost:.4f}",
                    f"{r.cost_per_million_tokens:.4f}",
                    r.notes,
                ]
            )


def export_json(rows: list, path: Path) -> None:
    data = [
        {
            "option": r.name,
            "monthly_cost_usd": round(r.monthly_cost, 4),
            "cost_per_million_tokens_usd": round(r.cost_per_million_tokens, 4),
            "notes": r.notes,
        }
        for r in sorted(rows, key=lambda r: r.monthly_cost)
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --------------------------------------------------------------------------
# Windows / NVIDIA GPU detection (best-effort, non-fatal)
# --------------------------------------------------------------------------


def _safe_float(value: str) -> Optional[float]:
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        return None


def detect_nvidia_gpu(runner: Callable = subprocess.run) -> Optional[dict]:
    """Detect an NVIDIA GPU via ``nvidia-smi`` (works on Windows and Linux).

    Returns a dict with name/memory/power info, or None if ``nvidia-smi``
    isn't installed, isn't on PATH, or returns no usable data. Callers must
    treat None as "detection unavailable" and fall back to manual input.
    """
    try:
        result = runner(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,power.draw,power.limit",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    first_line = result.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in first_line.split(",")]
    if len(parts) < 4:
        return None
    name, mem_total, power_draw, power_limit = parts[:4]
    return {
        "name": name,
        "memory_total_mib": _safe_float(mem_total),
        "power_draw_w": _safe_float(power_draw),
        "power_limit_w": _safe_float(power_limit),
    }


def measure_gpu_power_during(
    func: Callable, runner: Callable = subprocess.run, poll_interval: float = 0.5
) -> tuple:
    """Run ``func()`` while polling GPU power draw; return ``(result, peak_watts)``.

    ``peak_watts`` is the highest ``power.draw`` reading seen while ``func``
    was running, or None if no reading was available (no GPU, or ``func``
    finished before the first poll). This lets the benchmark step measure a
    real "under load" wattage instead of asking the user to guess it.
    """
    readings = []
    stop = threading.Event()

    def poll() -> None:
        while not stop.is_set():
            info = detect_nvidia_gpu(runner)
            if info and info.get("power_draw_w") is not None:
                readings.append(info["power_draw_w"])
            stop.wait(poll_interval)

    thread = threading.Thread(target=poll, daemon=True)
    thread.start()
    try:
        result = func()
    finally:
        stop.set()
        thread.join(timeout=poll_interval * 4)
    return result, (max(readings) if readings else None)


OCTOPUS_PRODUCTS_URL = "https://api.octopus.energy/v1/products/"


def fetch_octopus_agile_rate(
    region_letter: str = "C", timeout: float = 5.0
) -> Optional[float]:
    """Best-effort fetch of the current Octopus Agile unit rate (GBP/kWh).

    Octopus Agile product codes roll over every few months, so this looks
    the current one up rather than hardcoding it, then finds the
    half-hourly rate slot covering right now. Returns None on any failure
    (network, no matching product, parsing) so callers fall back to manual
    entry — this is a convenience lookup, not a requirement.
    """
    try:
        with urllib.request.urlopen(OCTOPUS_PRODUCTS_URL, timeout=timeout) as resp:
            products = json.loads(resp.read()).get("results", [])
        agile_codes = [
            p["code"] for p in products if "AGILE" in p.get("code", "").upper()
        ]
        if not agile_codes:
            return None
        product_code = agile_codes[0]
        tariff_code = f"E-1R-{product_code}-{region_letter}"
        rates_url = (
            f"https://api.octopus.energy/v1/products/{product_code}/"
            f"electricity-tariffs/{tariff_code}/standard-unit-rates/"
        )
        with urllib.request.urlopen(rates_url, timeout=timeout) as resp:
            rates = json.loads(resp.read()).get("results", [])
        now = datetime.now(timezone.utc)
        for rate in rates:
            valid_from = datetime.fromisoformat(
                rate["valid_from"].replace("Z", "+00:00")
            )
            valid_to_raw = rate.get("valid_to")
            valid_to = (
                datetime.fromisoformat(valid_to_raw.replace("Z", "+00:00"))
                if valid_to_raw
                else None
            )
            if valid_from <= now and (valid_to is None or now < valid_to):
                return rate["value_inc_vat"] / 100.0
        return None
    except Exception:  # noqa: BLE001 - best-effort, any failure just falls back
        return None


# Tried in order; each is a free, no-auth-required FX API. Frankfurter has
# moved domains before (frankfurter.app -> frankfurter.dev), and any single
# provider can be down or blocked on a given network, so falling through to
# the next one is more robust than depending on exactly one host.
FX_RATE_URL_TEMPLATES: tuple = (
    "https://api.frankfurter.dev/v1/latest?from={from_currency}&to={to_currency}",
    "https://api.frankfurter.app/v1/latest?from={from_currency}&to={to_currency}",
    "https://api.exchangerate.host/latest?base={from_currency}&symbols={to_currency}",
)


def fetch_fx_rate(
    from_currency: str, to_currency: str, timeout: float = 5.0
) -> Optional[float]:
    """Best-effort live exchange rate, trying each of ``FX_RATE_URL_TEMPLATES``.

    Returns None only if every provider fails (network, unknown currency,
    parsing) so callers fall back to manual entry rather than hardcoding a
    rate that goes stale.
    """
    for template in FX_RATE_URL_TEMPLATES:
        url = template.format(from_currency=from_currency, to_currency=to_currency)
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = json.loads(resp.read())
            return data["rates"][to_currency]
        except Exception:  # noqa: BLE001 - best-effort, try the next provider
            continue
    return None


# Rough street price (USD) and typical power draw under load (W) for common
# GPUs, matched by substring against a detected card's name. These are
# ballpark figures meant to prefill a realistic starting point instead of a
# one-size-fits-all guess — the interactive prompt still lets the user
# override either value if theirs differs.
GPU_COST_POWER_DEFAULTS: tuple = (
    ("RTX 4090", 1600.0, 450.0),
    ("RTX 4080 SUPER", 1000.0, 320.0),
    ("RTX 4080", 1000.0, 320.0),
    ("RTX 4070 TI SUPER", 800.0, 285.0),
    ("RTX 4070", 550.0, 200.0),
    ("RTX 3090 TI", 900.0, 450.0),
    ("RTX 3090", 800.0, 350.0),
    ("RTX 3080", 500.0, 320.0),
    ("RTX 3070", 400.0, 220.0),
    ("RTX 6000 ADA", 6800.0, 300.0),
    ("A100", 10000.0, 400.0),
    ("H100", 25000.0, 700.0),
)


def lookup_gpu_defaults(gpu_name: str) -> Optional[tuple]:
    """Best-effort ``(cost_usd, power_watts)`` defaults for a detected GPU.

    Matches by substring against ``GPU_COST_POWER_DEFAULTS`` so a detected
    card pre-fills a realistic price/power pair instead of a generic
    default unrelated to the actual hardware. Returns None on no match —
    callers fall back to a generic default and the prompt still lets the
    user override.
    """
    name = gpu_name.upper()
    for label, cost, power in GPU_COST_POWER_DEFAULTS:
        if label in name:
            return cost, power
    return None


def format_gpu_summary(gpu_info: dict) -> str:
    """Render a detected GPU's info for display.

    ``nvidia-smi`` reports ``[N/A]`` for some fields on certain cards/drivers
    (``_safe_float`` turns that into ``None``); numeric formatting on a bare
    ``None`` raises ``TypeError``, so each field is guarded independently
    rather than formatted unconditionally.
    """
    mem = gpu_info.get("memory_total_mib")
    mem_s = f"{mem:.0f} MiB VRAM" if mem is not None else "VRAM unknown"
    draw = gpu_info.get("power_draw_w")
    draw_s = f"{draw:.0f} W draw" if draw is not None else "power draw unknown"
    limit = gpu_info.get("power_limit_w")
    limit_s = f"{limit:.0f} W limit" if limit is not None else "power limit unknown"
    return f"{gpu_info['name']} ({mem_s}, {draw_s} / {limit_s})"


# --------------------------------------------------------------------------
# Local model discovery (best-effort, non-fatal)
# --------------------------------------------------------------------------


def list_ollama_models(base_url: str) -> list:
    """List every model pulled into the local Ollama install (``GET /api/tags``)."""
    _validate_http_url(base_url)
    req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", []) if "name" in m]


def list_running_ollama_models(base_url: str) -> list:
    """List models Ollama currently has loaded in memory (``GET /api/ps``).

    This is "what's actually loaded right now", which is the model any
    benchmark request will hit — a better default than the full installed
    list from ``list_ollama_models`` when both are available.
    """
    _validate_http_url(base_url)
    req = urllib.request.Request(f"{base_url.rstrip('/')}/api/ps", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", []) if "name" in m]


def list_openai_compatible_models(base_url: str, api_key: Optional[str] = None) -> list:
    """List models an OpenAI-compatible server reports as available (``GET /v1/models``)."""
    _validate_http_url(base_url)
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/models", headers=headers, method="GET"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["id"] for m in data.get("data", []) if "id" in m]


def discover_local_models(backend: str, base_url: str) -> list:
    """Best-effort list of model names/ids available on a local endpoint.

    For Ollama, currently-loaded models (if any) are preferred over the full
    installed list, since that's what a benchmark request will actually hit.
    Returns an empty list on any failure (unreachable endpoint, unexpected
    response shape, etc.) — callers should treat that as "ask the user
    manually", not as an error worth surfacing.
    """
    try:
        if backend == "ollama":
            running = list_running_ollama_models(base_url)
            return running or list_ollama_models(base_url)
        return list_openai_compatible_models(base_url)
    except Exception:  # noqa: BLE001 - best-effort, any failure just falls back
        return []


# --------------------------------------------------------------------------
# Optional local throughput benchmark (best-effort, non-fatal)
# --------------------------------------------------------------------------

BENCHMARK_PROMPT = (
    "Write a short, three-sentence paragraph describing the weather in an "
    "imaginary coastal town."
)


def _validate_http_url(base_url: str) -> None:
    """Reject non-http(s) base URLs before building a request from them.

    ``base_url`` comes straight from free-form user input; without this, a
    ``file://`` or other custom scheme would be passed through to
    ``urllib.request`` unchecked.
    """
    scheme = base_url.split("://", 1)[0].lower() if "://" in base_url else ""
    if scheme not in ("http", "https"):
        raise ValueError(
            f"base_url must start with http:// or https:// (got {base_url!r})"
        )


def benchmark_ollama(base_url: str, model: str, num_predict: int = 200) -> float:
    """Measure tokens/sec against a local Ollama server.

    Uses Ollama's ``eval_count``/``eval_duration`` fields, which measure
    generation only (excludes prompt processing) — the same basis this
    script uses elsewhere for local throughput. Not directly comparable to
    ``benchmark_openai_compatible``'s wall-clock measurement (see its
    docstring).
    """
    _validate_http_url(base_url)
    payload = json.dumps(
        {
            "model": model,
            "prompt": BENCHMARK_PROMPT,
            "stream": False,
            "options": {"num_predict": num_predict},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    eval_count = data.get("eval_count")
    eval_duration_ns = data.get("eval_duration")
    if not eval_count or not eval_duration_ns:
        raise ValueError("Ollama response missing eval_count/eval_duration")
    return eval_count / (eval_duration_ns / 1e9)


def benchmark_openai_compatible(
    base_url: str, model: str, api_key: Optional[str] = None, max_tokens: int = 200
) -> float:
    """Measure tokens/sec against a local OpenAI-compatible chat endpoint.

    Timing is wall-clock — it includes prompt processing and network
    round-trip, not generation alone — and falls back to a word-count
    approximation if the response has no ``usage.completion_tokens`` field.
    Both make this systematically lower and not directly comparable to
    ``benchmark_ollama``'s generation-only ``eval_duration`` measurement.
    """
    _validate_http_url(base_url)
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": BENCHMARK_PROMPT}],
            "max_tokens": max_tokens,
            "stream": False,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.monotonic() - start
    completion_tokens = (data.get("usage") or {}).get("completion_tokens")
    if not completion_tokens:
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        completion_tokens = max(1, len(text.split()))
    if elapsed <= 0:
        raise ValueError("Non-positive elapsed time measuring benchmark")
    return completion_tokens / elapsed


# --------------------------------------------------------------------------
# Interactive prompt helpers (thin I/O layer over the pure functions above)
# --------------------------------------------------------------------------


def prompt_float(
    prompt: str, default: Optional[float] = None, *, minimum: Optional[float] = None
) -> float:
    """Prompt for a float, re-asking on non-numeric input.

    ``minimum`` (exclusive-or-equal, i.e. ``value >= minimum``) rejects
    values that would blow up downstream math (e.g. a tokens/sec or
    lifetime-years of 0 raises ``ValueError`` deep in the cost calculation,
    discarding every answer the user already gave).
    """
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a number.")
            continue
        if minimum is not None and value < minimum:
            print(f"  Please enter a number >= {minimum}.")
            continue
        return value


def prompt_choice(prompt: str, choices: list, default: Optional[str] = None) -> str:
    choice_str = "/".join(choices)
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{prompt} ({choice_str}){suffix}: ").strip().lower()
        if not raw and default:
            return default
        if raw in choices:
            return raw
        print(f"  Please enter one of: {choice_str}")


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    raw = input(f"{prompt}{suffix}: ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")


def _prompt_custom_workload() -> Workload:
    while True:
        requests_per_day = prompt_float("Requests per day", default=1000, minimum=0)
        avg_input = prompt_float(
            "Average input tokens per request", default=500, minimum=0
        )
        avg_output = prompt_float(
            "Average output tokens per request", default=300, minimum=0
        )
        workload = Workload(requests_per_day, avg_input, avg_output)
        if workload.monthly_total_tokens > 0:
            return workload
        print(
            "  That produces zero total tokens/month — set requests per day and at "
            "least one of input/output tokens above zero. Let's try again."
        )


def interactive_workload() -> list:
    """Prompt for one or more workload scenarios to compare.

    Returns a list of ``(key, label, Workload)`` tuples — usually one, but
    "compare all presets" returns one per preset so the caller can print (and
    optionally export) a separate table per scenario.
    """
    print("\n== Workload ==")
    print(
        "How much traffic should this comparison assume? Guessing raw numbers "
        "cold is hard, so pick a preset scenario below, compare all of them at "
        "once, or enter your own numbers if none fit.\n"
    )
    for i, preset in enumerate(WORKLOAD_PRESETS, start=1):
        print(f"  {i}. {preset.label} — {preset.description}")
    all_option = len(WORKLOAD_PRESETS) + 1
    custom_option = len(WORKLOAD_PRESETS) + 2
    print(f"  {all_option}. Compare all of the above scenarios")
    print(f"  {custom_option}. Enter my own numbers")

    choices = [str(i) for i in range(1, custom_option + 1)]
    choice = int(prompt_choice("Choice", choices, default=str(all_option)))

    if choice <= len(WORKLOAD_PRESETS):
        preset = WORKLOAD_PRESETS[choice - 1]
        return [(preset.key, preset.label, preset.to_workload())]
    if choice == all_option:
        return [(p.key, p.label, p.to_workload()) for p in WORKLOAD_PRESETS]
    return [("custom", "Custom", _prompt_custom_workload())]


def interactive_local_setup() -> Callable[[Workload], list]:
    print("\n== Local setup ==")
    gpu_info = None
    if prompt_yes_no(
        "Attempt to auto-detect an NVIDIA GPU via nvidia-smi?", default=True
    ):
        gpu_info = detect_nvidia_gpu()
        if gpu_info:
            print(f"  Detected: {format_gpu_summary(gpu_info)}")
        else:
            print(
                "  No GPU detected (nvidia-smi not found or returned no data) — enter manually."
            )

    tokens_per_sec = None
    measured_load_power_w = None
    if prompt_yes_no(
        "Attempt to benchmark a running local model endpoint (Ollama or OpenAI-compatible)?",
        default=True,
    ):
        backend = prompt_choice("Backend", ["ollama", "openai"], default="ollama")
        base_url = (
            input("Base URL [http://localhost:11434]: ").strip()
            or "http://localhost:11434"
        )

        detected_models = discover_local_models(backend, base_url)
        default_model = detected_models[0] if detected_models else None
        if detected_models:
            print(f"  Detected models: {', '.join(detected_models)}")
        prompt_label = "Model name as served locally"
        if default_model:
            model = (
                input(f"{prompt_label} [{default_model}]: ").strip() or default_model
            )
        else:
            model = input(f"{prompt_label}: ").strip()
        measured_load_power_w = None
        try:
            if backend == "ollama":
                tokens_per_sec, measured_load_power_w = measure_gpu_power_during(
                    lambda: benchmark_ollama(base_url, model)
                )
            else:
                tokens_per_sec, measured_load_power_w = measure_gpu_power_during(
                    lambda: benchmark_openai_compatible(base_url, model)
                )
            print(f"  Measured throughput: {tokens_per_sec:.1f} tokens/sec")
        except (
            Exception
        ) as exc:  # noqa: BLE001 - best-effort, any failure just falls back
            print(f"  Benchmark failed ({exc}) — enter throughput manually.")
            tokens_per_sec = None

    if tokens_per_sec is None:
        tokens_per_sec = prompt_float(
            "Measured or estimated tokens/sec", default=40.0, minimum=0.001
        )

    print(
        "\n  How should the cost of the hardware itself count?\n"
        "    existing — You already have this PC/GPU for other reasons; only the extra\n"
        "               electricity it uses while running counts (most people, most of\n"
        "               the time).\n"
        "    buying   — You're weighing whether to buy hardware specifically for this.\n"
        "    rent     — You'd rent GPU time in the cloud instead of using your own machine.\n"
    )
    mode = prompt_choice(
        "Hardware mode", ["existing", "buying", "rent"], default="existing"
    )

    if mode == "buying":
        gpu_defaults = lookup_gpu_defaults(gpu_info["name"]) if gpu_info else None
        if gpu_defaults:
            default_cost, default_power = gpu_defaults
            print(
                f"  Using typical price/power for {gpu_info['name']}: "
                f"${default_cost:,.0f}, {default_power:.0f} W — override below if yours differs."
            )
        else:
            default_cost = 1600.0
            default_power = (
                gpu_info["power_limit_w"]
                if gpu_info and gpu_info.get("power_limit_w")
                else 450.0
            )
        hardware_cost = prompt_float(
            "Hardware cost (USD)", default=default_cost, minimum=0
        )
        lifetime_years = prompt_float(
            "Expected hardware lifetime (years)", default=3.0, minimum=0.001
        )
        power_watts = prompt_float(
            "Power draw under load (W)", default=default_power, minimum=0
        )
        electricity_rate = prompt_float(
            "Electricity rate (USD/kWh)", default=0.15, minimum=0
        )
        return lambda workload: [
            build_local_row(
                workload,
                tokens_per_sec,
                "own",
                hardware_cost=hardware_cost,
                lifetime_years=lifetime_years,
                power_watts=power_watts,
                electricity_rate_per_kwh=electricity_rate,
            )
        ]
    elif mode == "existing":
        idle_draw = gpu_info.get("power_draw_w") if gpu_info else None
        extra_default = None
        if measured_load_power_w is not None and idle_draw is not None:
            extra_default = max(measured_load_power_w - idle_draw, 0.0)
            print(
                f"  Extra power draw estimate: {extra_default:.0f} W (measured: load "
                f"{measured_load_power_w:.0f} W minus idle {idle_draw:.0f} W)"
            )
        elif gpu_info:
            gpu_defaults = lookup_gpu_defaults(gpu_info["name"])
            if gpu_defaults:
                _, typical_load_power = gpu_defaults
                baseline_idle = idle_draw if idle_draw is not None else 0.0
                extra_default = max(typical_load_power - baseline_idle, 0.0)
                print(
                    f"  Extra power draw estimate: {extra_default:.0f} W (calculated: "
                    f"{gpu_info['name']}'s typical load power {typical_load_power:.0f} W "
                    f"minus its current idle draw {baseline_idle:.0f} W — run the "
                    f"benchmark for a measured value instead of this estimate)"
                )
        if extra_default is None:
            extra_default = 250.0
            print(
                f"  Extra power draw estimate: {extra_default:.0f} W (generic fallback — "
                "no GPU detected and no benchmark run to measure from)"
            )

        print(
            "\n  Both cost bases are shown below, since which applies depends on why the\n"
            "  machine is on — you don't have to pick one up front.\n"
        )
        power_watts_extra = prompt_float(
            "Extra power draw while generating — GPU/CPU load above idle (W), "
            "for when the machine is already on for other reasons",
            default=extra_default,
            minimum=0,
        )
        # Rough allowance for the rest of the system (CPU, RAM, storage,
        # motherboard) beyond just the GPU, for when the whole machine's
        # power is attributable to this use because it wouldn't otherwise be on.
        power_watts_total = prompt_float(
            "Total system power draw while running — GPU plus the rest of the PC "
            "(W), for when it's only powered on to run this",
            default=power_watts_extra + 100.0,
            minimum=0,
        )

        electricity_rate = None
        if prompt_yes_no("Do you pay for electricity in GBP (e.g. UK)?", default=True):
            gbp_rate = None
            if prompt_yes_no(
                "Look up your current unit rate live from Octopus Agile?", default=True
            ):
                region = (
                    input("Octopus Energy region letter (A-P; C = London) [C]: ")
                    .strip()
                    .upper()
                    or "C"
                )
                gbp_rate = fetch_octopus_agile_rate(region)
                if gbp_rate is not None:
                    print(f"  Current Octopus Agile unit rate: £{gbp_rate:.4f}/kWh")
                else:
                    print(
                        "  Could not fetch a live Octopus Agile rate — enter manually."
                    )
            if gbp_rate is None:
                gbp_rate = prompt_float(
                    "Electricity rate (GBP/kWh)", default=0.2483, minimum=0
                )
            live_usd_per_gbp = fetch_fx_rate("GBP", "USD")
            if live_usd_per_gbp is not None:
                print(f"  Current GBP→USD exchange rate: {live_usd_per_gbp:.4f}")
            else:
                print("  Could not fetch a live exchange rate — enter manually.")
            usd_per_gbp = prompt_float(
                "GBP→USD exchange rate (so this can be compared against USD hosted "
                "pricing)",
                default=live_usd_per_gbp if live_usd_per_gbp is not None else 1.27,
                minimum=0,
            )
            electricity_rate = gbp_rate * usd_per_gbp
        else:
            electricity_rate = prompt_float(
                "Electricity rate (USD/kWh)", default=0.15, minimum=0
            )

        def build_existing_rows(workload: Workload) -> list:
            return [
                build_local_row(
                    workload,
                    tokens_per_sec,
                    "existing",
                    power_watts=power_watts_extra,
                    electricity_rate_per_kwh=electricity_rate,
                    name="Local (electricity only — machine already on for other reasons)",
                ),
                build_local_row(
                    workload,
                    tokens_per_sec,
                    "existing",
                    power_watts=power_watts_total,
                    electricity_rate_per_kwh=electricity_rate,
                    name="Local (electricity only — machine only powered on for this)",
                ),
            ]

        return build_existing_rows
    else:
        hourly_rate = prompt_float(
            "Rented GPU hourly rate (USD/hr)", default=2.50, minimum=0
        )
        return lambda workload: [
            build_local_row(workload, tokens_per_sec, "rent", hourly_rate=hourly_rate)
        ]


def interactive_provider_selection(pricing: dict) -> Optional[set]:
    print("\n== Hosted providers ==")
    print("Available models:")
    all_keys = []
    for provider_key, model_key, model_info in iter_models(pricing):
        full_key = f"{provider_key}/{model_key}"
        all_keys.append(full_key)
        print(f"  {full_key}: {model_info.get('display_name', full_key)}")
    if prompt_yes_no("Compare against all of the above?", default=True):
        return None
    raw = input("Enter comma-separated keys to include: ").strip()
    selected = {k.strip() for k in raw.split(",") if k.strip()}
    return selected or None


def run_interactive() -> int:
    print("LLM Cost Comparison — local vs hosted APIs")
    print("=" * 60)
    pricing = load_pricing()
    as_of = pricing.get("as_of", "unknown date")
    note = pricing.get("note", "")
    print(f"Hosted pricing as of {as_of}. {note}\n")

    scenarios = interactive_workload()
    local_row_builder = interactive_local_setup()
    selected = interactive_provider_selection(pricing)

    scenario_rows = {}
    for key, label, workload in scenarios:
        rows = list(local_row_builder(workload))
        rows.extend(build_hosted_rows(workload, pricing, selected))
        scenario_rows[key] = (label, workload, rows)

        print(f"\n== Results: {label} ==")
        print(
            f"Workload: {workload.requests_per_day:.0f} requests/day, "
            f"{workload.monthly_total_tokens:,.0f} total tokens/month"
        )
        print()
        print(render_table(rows))

    if prompt_yes_no("\nExport results to a file?", default=False):
        fmt = prompt_choice("Format", ["csv", "json"], default="csv")
        multiple = len(scenario_rows) > 1
        for key, (label, _workload, rows) in scenario_rows.items():
            default_name = (
                f"cost_comparison_{key}.{fmt}" if multiple else f"cost_comparison.{fmt}"
            )
            out_path = Path(
                input(f"Output path for '{label}' [{default_name}]: ").strip()
                or default_name
            )
            if fmt == "csv":
                export_csv(rows, out_path)
            else:
                export_json(rows, out_path)
            print(f"Wrote {out_path}")

    return 0


# --------------------------------------------------------------------------
# Non-interactive entry point (for scripting/CI/testing)
# --------------------------------------------------------------------------


def _require_keys(section: dict, required: list, context: str) -> None:
    missing = [k for k in required if k not in section]
    if missing:
        raise ConfigError(
            f"{context} config is missing required field(s): {', '.join(missing)}"
        )


def _require_numeric_fields(
    section: dict, fields: list, context: str, *, allow_zero: bool = True
) -> None:
    """Validate each field is a number, raising ``ConfigError`` if not.

    Without this, a stray string (e.g. a quoted ``"450"`` instead of ``450``)
    in ``hardware_cost``/``power_watts``/``hourly_rate`` etc. would fail with
    a raw ``TypeError`` deep inside the cost math instead of a clear,
    field-named error at config-load time.
    """
    bound = ">= 0" if allow_zero else "> 0"
    for field_name in fields:
        value = section[field_name]
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        if ok:
            ok = value >= 0 if allow_zero else value > 0
        if not ok:
            raise ConfigError(
                f"{context}.{field_name} must be a number {bound}, got {value!r}"
            )


def _resolve_workload_scenarios(config: dict) -> list:
    """Resolve the config's workload section to a list of scenarios.

    Exactly one of three shapes is accepted:
      * ``"workload"``: an explicit ``{requests_per_day, avg_input_tokens,
        avg_output_tokens}`` dict — the original, fully-custom shape.
      * ``"workload_preset"``: a single preset key (see ``WORKLOAD_PRESETS``).
      * ``"workload_presets"``: a list of preset keys, compared side by side.

    Returns a list of ``(key, label, Workload)`` tuples, mirroring
    ``interactive_workload``'s return shape so both paths share the same
    downstream printing/export logic.
    """
    provided = [
        k for k in ("workload", "workload_preset", "workload_presets") if k in config
    ]
    if not provided:
        raise ConfigError(
            "top-level config must include one of: workload, workload_preset, "
            "workload_presets"
        )
    if len(provided) > 1:
        raise ConfigError(
            f"top-level config must include only one of: workload, workload_preset, "
            f"workload_presets — got {', '.join(provided)}"
        )

    if "workload" in config:
        _require_keys(
            config["workload"],
            ["requests_per_day", "avg_input_tokens", "avg_output_tokens"],
            "workload",
        )
        for field_name in ("requests_per_day", "avg_input_tokens", "avg_output_tokens"):
            value = config["workload"][field_name]
            if not isinstance(value, (int, float)) or value < 0:
                raise ConfigError(
                    f"workload.{field_name} must be a non-negative number, got {value!r}"
                )
        try:
            workload = Workload(**config["workload"])
        except TypeError as exc:
            raise ConfigError(
                f"workload config has an unexpected field: {exc}"
            ) from exc
        if workload.monthly_total_tokens <= 0:
            raise ConfigError(
                "workload produces zero total tokens/month — set requests_per_day and "
                "at least one of avg_input_tokens/avg_output_tokens above zero"
            )
        return [("custom", "Custom", workload)]

    keys = (
        [config["workload_preset"]]
        if "workload_preset" in config
        else config["workload_presets"]
    )
    return [(p.key, p.label, p.to_workload()) for p in (get_preset(k) for k in keys)]


def run_non_interactive(
    config_path: Path, export_fmt: Optional[str], export_path: Optional[Path]
) -> int:
    """Run the comparison from a JSON config instead of interactive prompts.

    Config shape (most common case — hardware you already own):
        {
          "workload": {"requests_per_day": 1000, "avg_input_tokens": 500, "avg_output_tokens": 300},
          "local": {"mode": "existing", "power_watts": 450,
                     "electricity_rate_per_kwh": 0.15, "tokens_per_sec": 40},
          "pricing_file": "pricing.json",
          "selected_models": ["claude/opus-5", "deepseek/deepseek-v3"]
        }

    ``local.mode`` is one of:
      * ``"existing"`` — you already own the PC/GPU; only electricity counts
        (``power_watts``, ``electricity_rate_per_kwh``). Use the GPU/CPU's
        *extra* draw above idle if the machine is already on for other
        reasons, or the *whole system's* draw if it's only powered on to run
        this.
      * ``"own"`` — you're deciding whether to buy hardware specifically for
        this; adds ``hardware_cost`` and ``lifetime_years`` to amortize the
        purchase alongside electricity.
      * ``"rent"`` — a rented cloud GPU billed hourly (``hourly_rate``).

    In place of ``"workload"``, use ``"workload_preset": "<key>"`` for a
    single named scenario, or ``"workload_presets": ["<key>", ...]`` to
    compare several at once — see ``WORKLOAD_PRESETS`` for valid keys.
    Exactly one of ``workload`` / ``workload_preset`` / ``workload_presets``
    must be given.

    ``pricing_file``, if relative, is resolved against ``config_path``'s
    directory (not the process's working directory) so the example config
    works regardless of where the script is invoked from.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"config file {config_path} is not valid JSON: {exc}"
        ) from exc

    _require_keys(config, ["local"], "top-level")
    scenarios = _resolve_workload_scenarios(config)

    pricing_path = Path(config.get("pricing_file", DEFAULT_PRICING_PATH))
    if not pricing_path.is_absolute():
        pricing_path = config_path.parent / pricing_path
    try:
        pricing = load_pricing(pricing_path)
    except FileNotFoundError as exc:
        raise ConfigError(f"pricing file not found: {pricing_path}") from exc
    selected = set(config["selected_models"]) if config.get("selected_models") else None

    local_cfg = config["local"]
    _require_keys(local_cfg, ["mode", "tokens_per_sec"], "local")
    tokens_per_sec = local_cfg["tokens_per_sec"]
    if not isinstance(tokens_per_sec, (int, float)) or tokens_per_sec <= 0:
        raise ConfigError(
            f"local.tokens_per_sec must be a positive number, got {tokens_per_sec!r}"
        )
    mode = local_cfg["mode"]
    if mode == "own":
        _require_keys(
            local_cfg,
            [
                "hardware_cost",
                "lifetime_years",
                "power_watts",
                "electricity_rate_per_kwh",
            ],
            "local (mode=own)",
        )
        _require_numeric_fields(
            local_cfg,
            ["hardware_cost", "power_watts", "electricity_rate_per_kwh"],
            "local",
        )
        _require_numeric_fields(
            local_cfg, ["lifetime_years"], "local", allow_zero=False
        )

        def build_local(workload: Workload) -> ComparisonRow:
            return build_local_row(
                workload,
                local_cfg["tokens_per_sec"],
                "own",
                hardware_cost=local_cfg["hardware_cost"],
                lifetime_years=local_cfg["lifetime_years"],
                power_watts=local_cfg["power_watts"],
                electricity_rate_per_kwh=local_cfg["electricity_rate_per_kwh"],
            )

    elif mode == "existing":
        _require_keys(
            local_cfg,
            ["power_watts", "electricity_rate_per_kwh"],
            "local (mode=existing)",
        )
        _require_numeric_fields(
            local_cfg, ["power_watts", "electricity_rate_per_kwh"], "local"
        )

        def build_local(workload: Workload) -> ComparisonRow:
            return build_local_row(
                workload,
                local_cfg["tokens_per_sec"],
                "existing",
                power_watts=local_cfg["power_watts"],
                electricity_rate_per_kwh=local_cfg["electricity_rate_per_kwh"],
            )

    elif mode == "rent":
        _require_keys(local_cfg, ["hourly_rate"], "local (mode=rent)")
        _require_numeric_fields(local_cfg, ["hourly_rate"], "local")

        def build_local(workload: Workload) -> ComparisonRow:
            return build_local_row(
                workload,
                local_cfg["tokens_per_sec"],
                "rent",
                hourly_rate=local_cfg["hourly_rate"],
            )

    else:
        raise ConfigError(
            f"local.mode must be 'own', 'existing', or 'rent', got {mode!r}"
        )

    multiple = len(scenarios) > 1
    for key, label, workload in scenarios:
        rows = [build_local(workload)] + build_hosted_rows(workload, pricing, selected)
        print(f"\n== {label} ==")
        print(render_table(rows))

        if export_fmt and export_path:
            scenario_path = (
                export_path.with_name(f"{export_path.stem}_{key}{export_path.suffix}")
                if multiple
                else export_path
            )
            if export_fmt == "csv":
                export_csv(rows, scenario_path)
            else:
                export_json(rows, scenario_path)
            print(f"Wrote {scenario_path}")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Read all inputs from --config instead of prompting.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="JSON config file for --non-interactive mode (see run_non_interactive docstring).",
    )
    parser.add_argument(
        "--export", choices=["csv", "json"], help="Export results in this format."
    )
    parser.add_argument("--export-path", type=Path, help="Path to write the export to.")
    args = parser.parse_args(argv)

    if args.non_interactive:
        if not args.config:
            parser.error("--non-interactive requires --config")
        # --export without --export-path would otherwise silently export
        # nothing (run_non_interactive requires both to be truthy) — default
        # a path rather than let the flag be a no-op.
        if args.export and not args.export_path:
            args.export_path = Path(f"cost_comparison.{args.export}")
        try:
            return run_non_interactive(args.config, args.export, args.export_path)
        except ConfigError as exc:
            print(f"Config error: {exc}", file=sys.stderr)
            return 1

    if args.export or args.export_path:
        print(
            "Note: --export/--export-path only apply to --non-interactive mode; "
            "interactive mode asks about exporting at the end.",
            file=sys.stderr,
        )

    try:
        return run_interactive()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
