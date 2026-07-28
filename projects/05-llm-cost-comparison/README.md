# LLM Cost Comparison

Interactive script that estimates and compares the cost of running an LLM
**locally** (owned hardware or a rented cloud GPU) against **hosted APIs**
(DeepSeek, Claude), based on your own workload and, where possible, your own
measured hardware.

Resolves [#31](https://github.com/leonarduk/ai-systems-lab/issues/31).

## Why

Comparing local inference cost to hosted API pricing normally means manually
gathering GPU specs, power draw, measured throughput, and provider pricing,
then doing the arithmetic by hand each time. This script asks the questions,
runs what checks it can automatically, and prints a side-by-side table.

## Requirements

- Python 3.11+ (stdlib only — no `pip install` needed).
- Optional, for the best-effort checks:
  - `nvidia-smi` on PATH (ships with any NVIDIA driver install, including on
    Windows) to auto-detect GPU name/VRAM/power draw.
  - A running local model server (e.g. [Ollama](https://ollama.com) or an
    OpenAI-compatible endpoint like LM Studio) if you want the script to
    measure your actual tokens/sec instead of you estimating it.

Both checks are optional and degrade gracefully to manual input if
unavailable — the script works fine with neither.

## Usage

### Interactive (recommended)

```bash
python llm_cost_comparison.py
```

Walks through:
1. **Workload** — requests/day and average input/output tokens per request.
2. **Local setup** — optional GPU auto-detection, optional throughput
   benchmark against a local model server, then hardware cost/lifetime/power
   (owned) or hourly rate (rented cloud GPU).
3. **Hosted providers** — pick which models from `pricing.json` to compare
   against, or compare against all of them.
4. **Results** — a table sorted cheapest-first, with an option to export to
   CSV or JSON.

### Non-interactive (scripting / CI)

```bash
python llm_cost_comparison.py --non-interactive --config example_config.json \
    --export json --export-path out.json
```

See `example_config.json` for the config shape.

## How the numbers are computed

- **Hosted providers**: `monthly cost = (monthly input tokens / 1M × input rate) + (monthly output tokens / 1M × output rate)`, using rates from `pricing.json`.
- **Owned local hardware**: split into a *fixed* monthly cost (hardware price
  amortized over its expected lifetime — it ages whether it's busy or not)
  plus a *variable* cost (power draw × electricity rate × hours actually
  spent generating the workload's tokens).
- **Rented cloud GPU**: `hourly rate × hours needed for the workload` — no
  amortization, since you're not buying the hardware.
- All options are also expressed as a blended **$ per 1 million tokens**
  (input + output combined) so local and hosted costs are directly
  comparable regardless of your workload's input/output mix.

## Updating pricing

Hosted pricing changes over time. Edit `pricing.json` directly. Its shape is:

```json
{
  "as_of": "2026-07-28",
  "note": "free-text caveat shown to the user",
  "providers": {
    "<provider_key>": {
      "display_name": "...",
      "models": {
        "<model_key>": {
          "display_name": "...",
          "input_per_million": 0.0,
          "output_per_million": 0.0
        }
      }
    }
  }
}
```

`selected_models` (in a non-interactive config, or the interactive provider
picker) refers to models by `<provider_key>/<model_key>`. **DeepSeek's rates
in particular are approximate public figures and haven't been verified
against a live pricing page** — check the provider's pricing page before
relying on these numbers for a real decision.

## Tests

```bash
pip install pytest
pytest test_llm_cost_comparison.py -v
```

Tests cover the pure cost-calculation functions, pricing-file loading,
`nvidia-smi` output parsing (via a mocked subprocess runner — no GPU needed
to run the tests), table rendering, CSV/JSON export, and an end-to-end
non-interactive run. The interactive `input()` prompt flow is a thin wrapper
around these tested functions and isn't itself exercised by the test suite.

## Windows notes

- Works with the standard Windows Python installer — no extra dependencies.
- GPU auto-detection shells out to `nvidia-smi`, which is included with
  NVIDIA's Windows driver package and is normally already on `PATH`. If it
  isn't found, the script says so and falls back to asking for GPU specs
  manually.
- The optional local-endpoint benchmark works the same way on Windows as
  elsewhere — point it at `http://localhost:11434` for a local Ollama
  install, or your OpenAI-compatible server's base URL.
