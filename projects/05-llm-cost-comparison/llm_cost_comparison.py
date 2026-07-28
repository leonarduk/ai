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
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

DEFAULT_PRICING_PATH = Path(__file__).parent / "pricing.json"
DAYS_PER_MONTH = 30
HOURS_PER_MONTH = DAYS_PER_MONTH * 24


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


def hours_needed_for_workload(total_monthly_tokens: float, tokens_per_sec: float) -> float:
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


def local_monthly_cost_rented(hourly_rate: float, hours_needed_per_month: float) -> float:
    """Monthly cost for a rented cloud GPU billed per hour of usage."""
    return hourly_rate * hours_needed_per_month


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
) -> ComparisonRow:
    hours_needed = hours_needed_for_workload(workload.monthly_total_tokens, tokens_per_sec)
    if mode == "own":
        monthly_cost = local_monthly_cost_owned(
            hardware_cost, lifetime_years, power_watts, electricity_rate_per_kwh, hours_needed
        )
        name = "Local (owned hardware)"
    elif mode == "rent":
        monthly_cost = local_monthly_cost_rented(hourly_rate, hours_needed)
        name = "Local (rented cloud GPU)"
    else:
        raise ValueError(f"Unknown local cost mode: {mode!r}")
    per_million = cost_per_million_tokens(monthly_cost, workload.monthly_total_tokens)
    notes = f"~{hours_needed:.1f} compute-hrs/month at {tokens_per_sec:.1f} tok/s"
    return ComparisonRow(name, monthly_cost, per_million, notes)


def build_hosted_rows(workload: Workload, pricing: dict, selected: Optional[set] = None) -> list:
    """Build a ComparisonRow for each hosted model in ``pricing``.

    ``selected`` is an optional set of ``"provider/model"`` keys to restrict
    the comparison to; if None, every model in the pricing file is included.
    """
    rows = []
    for provider_key, model_key, model_info in iter_models(pricing):
        full_key = f"{provider_key}/{model_key}"
        if selected is not None and full_key not in selected:
            continue
        monthly_cost = hosted_monthly_cost(
            workload, model_info["input_per_million"], model_info["output_per_million"]
        )
        per_million = cost_per_million_tokens(monthly_cost, workload.monthly_total_tokens)
        display = model_info.get("display_name", full_key)
        rows.append(ComparisonRow(display, monthly_cost, per_million))
    return rows


def render_table(rows: list) -> str:
    """Render comparison rows as a plain-text table, cheapest first."""
    if not rows:
        return "(no rows to display)"
    rows_sorted = sorted(rows, key=lambda r: r.monthly_cost)
    name_w = max(len("Option"), max(len(r.name) for r in rows_sorted))
    cost_w = max(len("Monthly cost"), max(len(f"${r.monthly_cost:,.2f}") for r in rows_sorted))
    per_m_w = max(
        len("$/1M tokens"), max(len(f"${r.cost_per_million_tokens:,.2f}") for r in rows_sorted)
    )
    header = f"{'Option':<{name_w}}  {'Monthly cost':>{cost_w}}  {'$/1M tokens':>{per_m_w}}  Notes"
    lines = [header, "-" * len(header)]
    for r in rows_sorted:
        cost_s = f"${r.monthly_cost:,.2f}"
        per_m_s = f"${r.cost_per_million_tokens:,.2f}"
        lines.append(f"{r.name:<{name_w}}  {cost_s:>{cost_w}}  {per_m_s:>{per_m_w}}  {r.notes}")
    cheapest = rows_sorted[0]
    most_expensive = rows_sorted[-1]
    if most_expensive.monthly_cost > 0 and cheapest.monthly_cost > 0:
        multiple = most_expensive.monthly_cost / cheapest.monthly_cost
        lines.append("")
        lines.append(
            f"Cheapest: {cheapest.name} — most expensive option is {multiple:.1f}x its cost."
        )
    return "\n".join(lines)


def export_csv(rows: list, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["option", "monthly_cost_usd", "cost_per_million_tokens_usd", "notes"])
        for r in sorted(rows, key=lambda r: r.monthly_cost):
            writer.writerow([r.name, f"{r.monthly_cost:.4f}", f"{r.cost_per_million_tokens:.4f}", r.notes])


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


# --------------------------------------------------------------------------
# Optional local throughput benchmark (best-effort, non-fatal)
# --------------------------------------------------------------------------

BENCHMARK_PROMPT = (
    "Write a short, three-sentence paragraph describing the weather in an "
    "imaginary coastal town."
)


def benchmark_ollama(base_url: str, model: str, num_predict: int = 200) -> float:
    """Measure tokens/sec against a local Ollama server.

    Uses Ollama's ``eval_count``/``eval_duration`` fields, which measure
    generation only (excludes prompt processing) — the same basis this
    script uses elsewhere for local throughput.
    """
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

    Falls back to wall-clock timing with a word-count approximation if the
    response has no ``usage.completion_tokens`` field.
    """
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
        f"{base_url.rstrip('/')}/v1/chat/completions", data=payload, headers=headers, method="POST"
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


def prompt_float(prompt: str, default: Optional[float] = None) -> float:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return float(raw)
        except ValueError:
            print("  Please enter a number.")


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


def interactive_workload() -> Workload:
    print("\n== Workload ==")
    requests_per_day = prompt_float("Requests per day", default=1000)
    avg_input = prompt_float("Average input tokens per request", default=500)
    avg_output = prompt_float("Average output tokens per request", default=300)
    return Workload(requests_per_day, avg_input, avg_output)


def interactive_local_setup() -> ComparisonRow:
    print("\n== Local setup ==")
    gpu_info = None
    if prompt_yes_no("Attempt to auto-detect an NVIDIA GPU via nvidia-smi?", default=True):
        gpu_info = detect_nvidia_gpu()
        if gpu_info:
            print(
                f"  Detected: {gpu_info['name']} "
                f"({gpu_info['memory_total_mib']:.0f} MiB VRAM, "
                f"{gpu_info['power_draw_w']} W draw / {gpu_info['power_limit_w']} W limit)"
            )
        else:
            print("  No GPU detected (nvidia-smi not found or returned no data) — enter manually.")

    tokens_per_sec = None
    if prompt_yes_no(
        "Attempt to benchmark a running local model endpoint (Ollama or OpenAI-compatible)?",
        default=False,
    ):
        backend = prompt_choice("Backend", ["ollama", "openai"], default="ollama")
        base_url = input("Base URL [http://localhost:11434]: ").strip() or "http://localhost:11434"
        model = input("Model name as served locally: ").strip()
        try:
            if backend == "ollama":
                tokens_per_sec = benchmark_ollama(base_url, model)
            else:
                tokens_per_sec = benchmark_openai_compatible(base_url, model)
            print(f"  Measured throughput: {tokens_per_sec:.1f} tokens/sec")
        except Exception as exc:  # noqa: BLE001 - best-effort, any failure just falls back
            print(f"  Benchmark failed ({exc}) — enter throughput manually.")
            tokens_per_sec = None

    if tokens_per_sec is None:
        tokens_per_sec = prompt_float("Measured or estimated tokens/sec", default=40.0)

    mode = prompt_choice("Hardware mode", ["own", "rent"], default="own")
    if mode == "own":
        default_power = gpu_info["power_limit_w"] if gpu_info and gpu_info.get("power_limit_w") else 450.0
        hardware_cost = prompt_float("Hardware cost (USD)", default=1600.0)
        lifetime_years = prompt_float("Expected hardware lifetime (years)", default=3.0)
        power_watts = prompt_float("Power draw under load (W)", default=default_power)
        electricity_rate = prompt_float("Electricity rate (USD/kWh)", default=0.15)
        return lambda workload: build_local_row(
            workload,
            tokens_per_sec,
            "own",
            hardware_cost=hardware_cost,
            lifetime_years=lifetime_years,
            power_watts=power_watts,
            electricity_rate_per_kwh=electricity_rate,
        )
    else:
        hourly_rate = prompt_float("Rented GPU hourly rate (USD/hr)", default=2.50)
        return lambda workload: build_local_row(
            workload, tokens_per_sec, "rent", hourly_rate=hourly_rate
        )


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

    workload = interactive_workload()
    local_row_builder = interactive_local_setup()
    selected = interactive_provider_selection(pricing)

    rows = [local_row_builder(workload)]
    rows.extend(build_hosted_rows(workload, pricing, selected))

    print("\n== Results ==")
    print(
        f"Workload: {workload.requests_per_day:.0f} requests/day, "
        f"{workload.monthly_total_tokens:,.0f} total tokens/month"
    )
    print()
    print(render_table(rows))

    if prompt_yes_no("\nExport results to a file?", default=False):
        fmt = prompt_choice("Format", ["csv", "json"], default="csv")
        out_path = Path(input(f"Output path [cost_comparison.{fmt}]: ").strip() or f"cost_comparison.{fmt}")
        if fmt == "csv":
            export_csv(rows, out_path)
        else:
            export_json(rows, out_path)
        print(f"Wrote {out_path}")

    return 0


# --------------------------------------------------------------------------
# Non-interactive entry point (for scripting/CI/testing)
# --------------------------------------------------------------------------


def run_non_interactive(config_path: Path, export_fmt: Optional[str], export_path: Optional[Path]) -> int:
    """Run the comparison from a JSON config instead of interactive prompts.

    Config shape:
        {
          "workload": {"requests_per_day": 1000, "avg_input_tokens": 500, "avg_output_tokens": 300},
          "local": {"mode": "own", "hardware_cost": 1600, "lifetime_years": 3,
                     "power_watts": 450, "electricity_rate_per_kwh": 0.15,
                     "tokens_per_sec": 40},
          "pricing_file": "pricing.json",
          "selected_models": ["claude/opus-5", "deepseek/deepseek-v3"]
        }
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    workload = Workload(**config["workload"])
    pricing = load_pricing(Path(config.get("pricing_file", DEFAULT_PRICING_PATH)))
    selected = set(config["selected_models"]) if config.get("selected_models") else None

    local_cfg = config["local"]
    mode = local_cfg["mode"]
    if mode == "own":
        local_row = build_local_row(
            workload,
            local_cfg["tokens_per_sec"],
            "own",
            hardware_cost=local_cfg["hardware_cost"],
            lifetime_years=local_cfg["lifetime_years"],
            power_watts=local_cfg["power_watts"],
            electricity_rate_per_kwh=local_cfg["electricity_rate_per_kwh"],
        )
    else:
        local_row = build_local_row(
            workload, local_cfg["tokens_per_sec"], "rent", hourly_rate=local_cfg["hourly_rate"]
        )

    rows = [local_row] + build_hosted_rows(workload, pricing, selected)
    print(render_table(rows))

    if export_fmt and export_path:
        if export_fmt == "csv":
            export_csv(rows, export_path)
        else:
            export_json(rows, export_path)
        print(f"\nWrote {export_path}")
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
    parser.add_argument("--export", choices=["csv", "json"], help="Export results in this format.")
    parser.add_argument("--export-path", type=Path, help="Path to write the export to.")
    args = parser.parse_args(argv)

    if args.non_interactive:
        if not args.config:
            parser.error("--non-interactive requires --config")
        return run_non_interactive(args.config, args.export, args.export_path)

    try:
        return run_interactive()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
