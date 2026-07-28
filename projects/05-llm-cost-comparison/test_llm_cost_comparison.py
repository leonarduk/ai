"""Tests for llm_cost_comparison.py.

Covers the pure cost-calculation functions, pricing/config loading, GPU
detection parsing (with a mocked subprocess runner), and export helpers.
Interactive input() flows are intentionally not exercised here — the
interactive functions are thin wrappers over the tested pure functions.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import llm_cost_comparison as m

# --------------------------------------------------------------------------
# Workload
# --------------------------------------------------------------------------


def test_workload_monthly_totals():
    w = m.Workload(requests_per_day=1000, avg_input_tokens=500, avg_output_tokens=300)
    assert w.monthly_input_tokens == 1000 * 500 * 30
    assert w.monthly_output_tokens == 1000 * 300 * 30
    assert w.monthly_total_tokens == w.monthly_input_tokens + w.monthly_output_tokens


# --------------------------------------------------------------------------
# Hosted cost
# --------------------------------------------------------------------------


def test_hosted_monthly_cost():
    w = m.Workload(
        requests_per_day=1000, avg_input_tokens=1_000_000 / 1000, avg_output_tokens=0
    )
    # 1 request/day-equivalent scaling chosen so monthly input tokens == 30M exactly
    cost = m.hosted_monthly_cost(w, input_per_million=2.0, output_per_million=10.0)
    assert cost == pytest.approx(30_000_000 / 1_000_000 * 2.0)


def test_hosted_monthly_cost_combines_input_and_output():
    w = m.Workload(requests_per_day=100, avg_input_tokens=100, avg_output_tokens=50)
    cost = m.hosted_monthly_cost(w, input_per_million=3.0, output_per_million=15.0)
    expected = (w.monthly_input_tokens / 1_000_000 * 3.0) + (
        w.monthly_output_tokens / 1_000_000 * 15.0
    )
    assert cost == pytest.approx(expected)


# --------------------------------------------------------------------------
# Local cost math
# --------------------------------------------------------------------------


def test_hours_needed_for_workload():
    # 3,600,000 tokens at 1000 tok/s -> 3,600,000 / (1000*3600) = 1 hour
    hours = m.hours_needed_for_workload(
        total_monthly_tokens=3_600_000, tokens_per_sec=1000
    )
    assert hours == pytest.approx(1.0)


def test_hours_needed_for_workload_rejects_nonpositive_rate():
    with pytest.raises(ValueError):
        m.hours_needed_for_workload(1000, 0)


def test_local_monthly_cost_owned_splits_fixed_and_variable():
    # $3600 hardware / 3 years -> $100/month fixed, regardless of usage
    cost_idle = m.local_monthly_cost_owned(
        hardware_cost=3600,
        lifetime_years=3,
        power_watts=450,
        electricity_rate_per_kwh=0.15,
        hours_needed_per_month=0,
    )
    assert cost_idle == pytest.approx(100.0)

    cost_used = m.local_monthly_cost_owned(
        hardware_cost=3600,
        lifetime_years=3,
        power_watts=1000,  # 1 kW for easy math
        electricity_rate_per_kwh=0.10,
        hours_needed_per_month=10,
    )
    # fixed 100 + variable (1kW * $0.10/hr * 10hr) = 100 + 1 = 101
    assert cost_used == pytest.approx(101.0)


def test_local_monthly_cost_owned_rejects_zero_lifetime():
    with pytest.raises(ValueError):
        m.local_monthly_cost_owned(1000, 0, 100, 0.1, 10)


def test_local_monthly_cost_rented():
    assert m.local_monthly_cost_rented(
        hourly_rate=2.5, hours_needed_per_month=40
    ) == pytest.approx(100.0)


def test_cost_per_million_tokens():
    assert m.cost_per_million_tokens(
        monthly_cost=50, monthly_total_tokens=25_000_000
    ) == pytest.approx(2.0)


def test_cost_per_million_tokens_rejects_zero_tokens():
    with pytest.raises(ValueError):
        m.cost_per_million_tokens(50, 0)


# --------------------------------------------------------------------------
# Comparison rows
# --------------------------------------------------------------------------


def test_build_local_row_owned():
    w = m.Workload(requests_per_day=100, avg_input_tokens=500, avg_output_tokens=500)
    row = m.build_local_row(
        w,
        tokens_per_sec=100,
        mode="own",
        hardware_cost=3600,
        lifetime_years=3,
        power_watts=450,
        electricity_rate_per_kwh=0.15,
    )
    assert row.name == "Local (owned hardware)"
    assert row.monthly_cost > 0
    assert row.cost_per_million_tokens > 0
    assert "compute-hrs/month" in row.notes


def test_build_local_row_rented():
    w = m.Workload(requests_per_day=100, avg_input_tokens=500, avg_output_tokens=500)
    row = m.build_local_row(w, tokens_per_sec=100, mode="rent", hourly_rate=2.0)
    assert row.name == "Local (rented cloud GPU)"
    assert row.monthly_cost > 0


def test_build_local_row_rejects_unknown_mode():
    w = m.Workload(100, 500, 500)
    with pytest.raises(ValueError):
        m.build_local_row(w, tokens_per_sec=100, mode="bogus")


def test_build_hosted_rows_all_and_filtered(tmp_path):
    pricing = {
        "providers": {
            "claude": {
                "models": {
                    "opus-5": {
                        "display_name": "Claude Opus 5",
                        "input_per_million": 5.0,
                        "output_per_million": 25.0,
                    },
                    "haiku-4.5": {
                        "display_name": "Claude Haiku 4.5",
                        "input_per_million": 1.0,
                        "output_per_million": 5.0,
                    },
                }
            },
            "deepseek": {
                "models": {
                    "deepseek-v3": {
                        "display_name": "DeepSeek-V3",
                        "input_per_million": 0.27,
                        "output_per_million": 1.10,
                    }
                }
            },
        }
    }
    w = m.Workload(1000, 500, 300)

    all_rows = m.build_hosted_rows(w, pricing)
    assert len(all_rows) == 3
    names = {r.name for r in all_rows}
    assert names == {"Claude Opus 5", "Claude Haiku 4.5", "DeepSeek-V3"}

    filtered = m.build_hosted_rows(w, pricing, selected={"claude/haiku-4.5"})
    assert len(filtered) == 1
    assert filtered[0].name == "Claude Haiku 4.5"

    # Haiku should be cheaper than Opus for the same workload
    haiku_cost = next(r.monthly_cost for r in all_rows if r.name == "Claude Haiku 4.5")
    opus_cost = next(r.monthly_cost for r in all_rows if r.name == "Claude Opus 5")
    assert haiku_cost < opus_cost


# --------------------------------------------------------------------------
# Real pricing.json shipped alongside the script
# --------------------------------------------------------------------------


def test_load_shipped_pricing_file_is_well_formed():
    pricing = m.load_pricing()
    assert "providers" in pricing
    assert "claude" in pricing["providers"]
    assert "deepseek" in pricing["providers"]
    models = list(m.iter_models(pricing))
    assert len(models) > 0
    for _, _, info in models:
        assert info["input_per_million"] > 0
        assert info["output_per_million"] > 0


# --------------------------------------------------------------------------
# Rendering / export
# --------------------------------------------------------------------------


def test_render_table_orders_cheapest_first_and_notes_multiple():
    rows = [
        m.ComparisonRow("Expensive", monthly_cost=100.0, cost_per_million_tokens=10.0),
        m.ComparisonRow("Cheap", monthly_cost=10.0, cost_per_million_tokens=1.0),
    ]
    table = m.render_table(rows)
    assert table.index("Cheap") < table.index("Expensive")
    assert "10.0x" in table


def test_render_table_empty():
    assert "no rows" in m.render_table([])


def test_export_csv_and_json(tmp_path: Path):
    rows = [
        m.ComparisonRow("A", 10.0, 1.0, "note-a"),
        m.ComparisonRow("B", 5.0, 0.5, "note-b"),
    ]

    csv_path = tmp_path / "out.csv"
    m.export_csv(rows, csv_path)
    csv_content = csv_path.read_text(encoding="utf-8")
    assert "option" in csv_content
    assert "A" in csv_content and "B" in csv_content
    # cheapest (B) should be written before A
    assert csv_content.index("B") < csv_content.index("A")

    json_path = tmp_path / "out.json"
    m.export_json(rows, json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data[0]["option"] == "B"
    assert data[1]["option"] == "A"
    assert data[0]["monthly_cost_usd"] == 5.0


# --------------------------------------------------------------------------
# GPU detection (mocked subprocess — no real nvidia-smi needed to test)
# --------------------------------------------------------------------------


class _FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode


def test_detect_nvidia_gpu_parses_output():
    def fake_runner(*args, **kwargs):
        return _FakeCompletedProcess("NVIDIA GeForce RTX 4090, 24564, 210.5, 450\n")

    info = m.detect_nvidia_gpu(runner=fake_runner)
    assert info == {
        "name": "NVIDIA GeForce RTX 4090",
        "memory_total_mib": 24564.0,
        "power_draw_w": 210.5,
        "power_limit_w": 450.0,
    }


def test_detect_nvidia_gpu_handles_na_power_draw():
    def fake_runner(*args, **kwargs):
        return _FakeCompletedProcess("NVIDIA GeForce RTX 3060, 12288, [N/A], 170\n")

    info = m.detect_nvidia_gpu(runner=fake_runner)
    assert info["power_draw_w"] is None
    assert info["power_limit_w"] == 170.0


def test_detect_nvidia_gpu_returns_none_when_not_found():
    def fake_runner(*args, **kwargs):
        raise FileNotFoundError()

    assert m.detect_nvidia_gpu(runner=fake_runner) is None


def test_detect_nvidia_gpu_returns_none_on_nonzero_exit():
    def fake_runner(*args, **kwargs):
        return _FakeCompletedProcess("", returncode=1)

    assert m.detect_nvidia_gpu(runner=fake_runner) is None


def test_detect_nvidia_gpu_returns_none_on_timeout():
    def fake_runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=5)

    assert m.detect_nvidia_gpu(runner=fake_runner) is None


def test_format_gpu_summary_with_all_fields():
    info = {
        "name": "NVIDIA GeForce RTX 4090",
        "memory_total_mib": 24564.0,
        "power_draw_w": 210.5,
        "power_limit_w": 450.0,
    }
    summary = m.format_gpu_summary(info)
    assert "NVIDIA GeForce RTX 4090" in summary
    assert "24564 MiB VRAM" in summary
    assert "210 W draw" in summary
    assert "450 W limit" in summary


def test_format_gpu_summary_handles_none_fields_without_crashing():
    # Regression test: nvidia-smi reporting "[N/A]" (parsed to None by
    # _safe_float) used to crash with TypeError on f"{None:.0f}".
    info = {
        "name": "NVIDIA GeForce RTX 3060",
        "memory_total_mib": None,
        "power_draw_w": None,
        "power_limit_w": 170.0,
    }
    summary = m.format_gpu_summary(info)
    assert "VRAM unknown" in summary
    assert "power draw unknown" in summary
    assert "170 W limit" in summary


# --------------------------------------------------------------------------
# Non-interactive end-to-end run
# --------------------------------------------------------------------------


def test_run_non_interactive_end_to_end(tmp_path: Path, capsys):
    pricing_path = tmp_path / "pricing.json"
    pricing_path.write_text(
        json.dumps(
            {
                "providers": {
                    "claude": {
                        "models": {
                            "opus-5": {
                                "display_name": "Claude Opus 5",
                                "input_per_million": 5.0,
                                "output_per_million": 25.0,
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {
            "mode": "own",
            "hardware_cost": 1600,
            "lifetime_years": 3,
            "power_watts": 450,
            "electricity_rate_per_kwh": 0.15,
            "tokens_per_sec": 40,
        },
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    export_path = tmp_path / "out.json"
    exit_code = m.run_non_interactive(
        config_path, export_fmt="json", export_path=export_path
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Local (owned hardware)" in out
    assert "Claude Opus 5" in out
    assert export_path.exists()
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert {row["option"] for row in exported} == {
        "Local (owned hardware)",
        "Claude Opus 5",
    }


# --------------------------------------------------------------------------
# Benchmark helpers (mocked urllib — no real server needed)
# --------------------------------------------------------------------------


def test_validate_http_url_accepts_http_and_https():
    m._validate_http_url("http://localhost:11434")
    m._validate_http_url("https://example.com")


def test_validate_http_url_rejects_other_schemes():
    with pytest.raises(ValueError):
        m._validate_http_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        m._validate_http_url("not-a-url")


class _FakeHTTPResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_benchmark_ollama_computes_tokens_per_sec(monkeypatch):
    body = json.dumps({"eval_count": 100, "eval_duration": 2_000_000_000}).encode(
        "utf-8"
    )

    def fake_urlopen(req, timeout=None):
        return _FakeHTTPResponse(body)

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    tokens_per_sec = m.benchmark_ollama("http://localhost:11434", "llama3")
    # 100 tokens / 2 seconds = 50 tok/s
    assert tokens_per_sec == pytest.approx(50.0)


def test_benchmark_ollama_raises_on_missing_fields(monkeypatch):
    body = json.dumps({"response": "no eval fields here"}).encode("utf-8")

    def fake_urlopen(req, timeout=None):
        return _FakeHTTPResponse(body)

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError):
        m.benchmark_ollama("http://localhost:11434", "llama3")


def test_benchmark_ollama_rejects_non_http_url():
    with pytest.raises(ValueError):
        m.benchmark_ollama("file:///etc/passwd", "llama3")


def test_benchmark_openai_compatible_uses_usage_completion_tokens(monkeypatch):
    body = json.dumps(
        {
            "choices": [{"message": {"content": "irrelevant"}}],
            "usage": {"completion_tokens": 42},
        }
    ).encode("utf-8")

    times = iter([100.0, 100.5])  # 0.5s elapsed

    def fake_urlopen(req, timeout=None):
        return _FakeHTTPResponse(body)

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(m.time, "monotonic", lambda: next(times))

    tokens_per_sec = m.benchmark_openai_compatible(
        "http://localhost:1234", "some-model"
    )
    assert tokens_per_sec == pytest.approx(42 / 0.5)


def test_benchmark_openai_compatible_falls_back_to_word_count(monkeypatch):
    body = json.dumps(
        {"choices": [{"message": {"content": "one two three four"}}]}
    ).encode("utf-8")

    times = iter([0.0, 1.0])  # 1s elapsed

    def fake_urlopen(req, timeout=None):
        return _FakeHTTPResponse(body)

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(m.time, "monotonic", lambda: next(times))

    tokens_per_sec = m.benchmark_openai_compatible(
        "http://localhost:1234", "some-model"
    )
    assert tokens_per_sec == pytest.approx(4.0)  # 4 words / 1s


def test_benchmark_openai_compatible_rejects_non_http_url():
    with pytest.raises(ValueError):
        m.benchmark_openai_compatible("ftp://example.com", "some-model")


# --------------------------------------------------------------------------
# prompt_float minimum enforcement
# --------------------------------------------------------------------------


def test_prompt_float_rejects_below_minimum(monkeypatch, capsys):
    answers = iter(["0", "-5", "10"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    value = m.prompt_float("Tokens/sec", minimum=0.001)
    assert value == 10.0
    out = capsys.readouterr().out
    assert out.count(">= 0.001") == 2  # rejected "0" and "-5" before accepting "10"


def test_prompt_float_accepts_default_without_minimum_check(monkeypatch):
    # An empty answer takes the default even if a minimum is set on the
    # default itself is trusted (defaults are author-supplied, not
    # attacker/user-supplied).
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert m.prompt_float("x", default=5.0, minimum=1.0) == 5.0


# --------------------------------------------------------------------------
# Non-interactive config validation
# --------------------------------------------------------------------------


def _write_pricing(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "claude": {
                        "models": {
                            "opus-5": {
                                "display_name": "Claude Opus 5",
                                "input_per_million": 5.0,
                                "output_per_million": 25.0,
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def test_run_non_interactive_rent_mode(tmp_path: Path, capsys):
    pricing_path = tmp_path / "pricing.json"
    _write_pricing(pricing_path)
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "rent", "tokens_per_sec": 40, "hourly_rate": 2.5},
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = m.run_non_interactive(config_path, export_fmt=None, export_path=None)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Local (rented cloud GPU)" in out


def test_run_non_interactive_rent_mode_missing_hourly_rate_raises_config_error(
    tmp_path: Path,
):
    pricing_path = tmp_path / "pricing.json"
    _write_pricing(pricing_path)
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "rent", "tokens_per_sec": 40},  # hourly_rate omitted
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(m.ConfigError, match="hourly_rate"):
        m.run_non_interactive(config_path, export_fmt=None, export_path=None)


def test_run_non_interactive_missing_workload_field_raises_config_error(tmp_path: Path):
    pricing_path = tmp_path / "pricing.json"
    _write_pricing(pricing_path)
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
        },  # avg_output_tokens missing
        "local": {
            "mode": "own",
            "tokens_per_sec": 40,
            "hardware_cost": 1600,
            "lifetime_years": 3,
            "power_watts": 450,
            "electricity_rate_per_kwh": 0.15,
        },
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(m.ConfigError, match="avg_output_tokens"):
        m.run_non_interactive(config_path, export_fmt=None, export_path=None)


def test_run_non_interactive_unknown_mode_raises_config_error(tmp_path: Path):
    pricing_path = tmp_path / "pricing.json"
    _write_pricing(pricing_path)
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "bogus", "tokens_per_sec": 40},
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(m.ConfigError, match="own.*rent"):
        m.run_non_interactive(config_path, export_fmt=None, export_path=None)


def test_run_non_interactive_resolves_relative_pricing_file_against_config_dir(
    tmp_path: Path, capsys
):
    # pricing.json lives next to the config file, not the process cwd.
    subdir = tmp_path / "configs"
    subdir.mkdir()
    _write_pricing(subdir / "pricing.json")

    config_path = subdir / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "rent", "tokens_per_sec": 40, "hourly_rate": 2.5},
        "pricing_file": "pricing.json",  # relative — must resolve against config_path.parent
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = m.run_non_interactive(config_path, export_fmt=None, export_path=None)
    assert exit_code == 0
    assert "Claude Opus 5" in capsys.readouterr().out


# --------------------------------------------------------------------------
# main() CLI export-flag handling
# --------------------------------------------------------------------------


def test_main_non_interactive_export_without_path_defaults(
    tmp_path: Path, monkeypatch, capsys
):
    pricing_path = tmp_path / "pricing.json"
    _write_pricing(pricing_path)
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "rent", "tokens_per_sec": 40, "hourly_rate": 2.5},
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    exit_code = m.main(
        ["--non-interactive", "--config", str(config_path), "--export", "csv"]
    )
    assert exit_code == 0
    assert (tmp_path / "cost_comparison.csv").exists()


def test_main_non_interactive_config_error_reports_and_exits_nonzero(
    tmp_path: Path, capsys
):
    pricing_path = tmp_path / "pricing.json"
    _write_pricing(pricing_path)
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "rent", "tokens_per_sec": 40},  # missing hourly_rate
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = m.main(["--non-interactive", "--config", str(config_path)])
    assert exit_code == 1
    assert "hourly_rate" in capsys.readouterr().err


def test_run_non_interactive_missing_pricing_file_raises_config_error(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "rent", "tokens_per_sec": 40, "hourly_rate": 2.5},
        "pricing_file": "does_not_exist.json",
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(m.ConfigError, match="pricing file not found"):
        m.run_non_interactive(config_path, export_fmt=None, export_path=None)


@pytest.mark.parametrize("bad_value", [0, -5, "fast"])
def test_run_non_interactive_rejects_nonpositive_tokens_per_sec(
    tmp_path: Path, bad_value
):
    pricing_path = tmp_path / "pricing.json"
    _write_pricing(pricing_path)
    config_path = tmp_path / "config.json"
    config = {
        "workload": {
            "requests_per_day": 1000,
            "avg_input_tokens": 500,
            "avg_output_tokens": 300,
        },
        "local": {"mode": "rent", "tokens_per_sec": bad_value, "hourly_rate": 2.5},
        "pricing_file": str(pricing_path),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(m.ConfigError, match="tokens_per_sec"):
        m.run_non_interactive(config_path, export_fmt=None, export_path=None)
