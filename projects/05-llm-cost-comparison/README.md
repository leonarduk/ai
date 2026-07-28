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
    measure your actual tokens/sec instead of you estimating it, and to list
    which model is currently loaded (Ollama) or available (OpenAI-compatible)
    so you don't have to type its name from memory.

Both checks are optional and degrade gracefully to manual input if
unavailable — the script works fine with neither.

## Usage

### Interactive (recommended)

```bash
python llm_cost_comparison.py
```

Walks through:
1. **Workload** — pick a named traffic scenario ("casual personal use",
   "autonomous coding agent", etc.), compare all of them at once, or enter
   your own numbers if none fit. No need to guess requests/day cold.
2. **Local setup** — optional GPU auto-detection (which also prefills a
   realistic hardware price/power for that card), optional throughput
   benchmark against a local model server (which lists what's actually
   loaded so you don't have to type a model name blind, and — while it
   runs — measures the GPU's power draw under load so the "electricity
   only" mode below doesn't need a guessed wattage), then a choice of
   hardware cost basis (see below).
3. **Hosted providers** — pick which models from `pricing.json` to compare
   against, or compare against all of them.
4. **Results** — if you picked more than one scenario, one matrix table: one
   row per option, one column per scenario's monthly cost, plus a single
   `$/1M tokens` column (that rate doesn't change with workload size, so
   it's shown once instead of repeated per scenario). A single-scenario run
   gets a plain cheapest-first table instead. Exporting writes one CSV/JSON
   file with a `scenario` column either way, so a spreadsheet or script can
   filter or pivot across scenarios.

### Non-interactive (scripting / CI)

```bash
python llm_cost_comparison.py --non-interactive --config example_config.json \
    --export json --export-path out.json
```

See `example_config.json` (workload presets, hardware you already own) and
`example_config_buying_hardware.json` (explicit workload, buying new
hardware) for the config shapes.

## Traffic scenarios (workload presets)

Guessing "requests per day" and "average input tokens per request" cold is a
bad starting point if you've never measured your own usage. Instead of
asking for those numbers directly, the script offers named scenarios in
plain language:

| Preset key        | What it represents                                                             |
| ------------------ | ------------------------------------------------------------------------------ |
| `casual`            | A handful of questions a day, like using it instead of a search engine.       |
| `daily_assistant`   | Used on and off throughout the workday for drafting, research, quick coding.  |
| `coding_agent`      | An autonomous agent that reads files and runs commands on its own — large input tokens per turn since it re-sends file/context content. |
| `team_tool`         | A shared assistant used by a small team (5-20 people) all day.               |
| `production_app`    | A live app serving many users' requests around the clock.                    |

Pick one, compare all of them side by side, or fall back to entering your
own numbers. In a non-interactive config, use `"workload_preset": "<key>"`
for one scenario or `"workload_presets": ["<key>", ...]` to compare several
— see `WORKLOAD_PRESETS` in `llm_cost_comparison.py` for the exact
requests/day and token counts behind each one.

## How the numbers are computed

- **Hosted providers**: `monthly cost = (monthly input tokens / 1M × input rate) + (monthly output tokens / 1M × output rate)`, using rates from `pricing.json`.
- **Local — hardware you already own** (`existing` mode, the common case,
  interactive only): **electricity only**, no amortization — the machine's
  cost is sunk regardless of whether you run an LLM on it. Since which power
  basis applies depends on why the machine happens to be on, the interactive
  flow computes and shows **both** as separate rows rather than asking you
  to guess up front:
  - *Machine already on for other reasons* → the **extra** power the
    GPU/CPU draw under load, above idle. If a benchmark ran, this is
    measured automatically (peak power during the benchmark minus the idle
    reading taken at GPU detection) instead of guessed.
  - *Machine only powered on to run this* → the **whole system's** draw
    while running, since the entire session's electricity is attributable
    to this use (measured extra draw plus a fixed allowance for the rest of
    the PC).
  - Electricity rate can be entered in USD/kWh, or in GBP/kWh — including a
    live lookup of the current UK Octopus Agile unit rate. All cost math is
    still done internally in USD (hosted pricing is USD-denominated), using
    a live exchange rate (Frankfurter, exchangerate.host, or Yahoo Finance as
    fallbacks, in that order), but **the whole table — local and hosted rows
    alike — is displayed and exported in GBP** whenever you choose GBP, not
    just the local electricity figure.
  - The non-interactive config still takes a single `power_watts` — pick
    whichever basis applies to your situation.
- **Feasibility check**: if the workload needs more compute-hours per month
  than actually exist in a month (a slow local setup can't keep up with a
  high-volume workload in real time), the monthly-cost column shows `n/a`
  instead of a dollar figure, both on screen and in CSV/JSON exports. That
  number would otherwise be a straight-line extrapolation past the hours
  that physically exist in a month — e.g. "£1,590/month" for a laptop that
  would need to run 62 months' worth of hours in one month, which can read
  as a real bill (and can even look like it costs more per month than the
  hardware would cost to buy outright) when it isn't one. The `$/1M tokens`
  rate is still shown and still real even when infeasible: it's
  workload-independent (monthly cost scales with tokens, so the ratio
  doesn't), so it's a genuine per-token rate regardless of whether the
  workload's total volume is achievable. An infeasible option is also never
  ranked as "cheapest".
- **Local — buying new hardware** (`own` mode): split into a *fixed* monthly
  cost (hardware price amortized over its expected lifetime — it ages
  whether it's busy or not) plus the same *variable* electricity cost as
  above. GPU auto-detection prefills a realistic price/power pair for common
  cards instead of one generic guess.
- **Local — rented cloud GPU** (`rent` mode): `hourly rate × hours needed for
  the workload` — no amortization, since you're not buying the hardware.
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

Tests cover the pure cost-calculation functions (including the "existing
hardware" electricity-only mode), workload presets, pricing-file loading,
`nvidia-smi` output parsing and GPU price/power lookup (via a mocked
subprocess runner — no GPU needed to run the tests), local model discovery
(via mocked HTTP responses — no Ollama/LM Studio needed), table rendering,
CSV/JSON export, and end-to-end non-interactive runs (including multiple
preset scenarios in one run). The interactive `input()` prompt flow — the
workload/hardware-mode menus included — is exercised with a monkeypatched
`input()` where it's simple to script (e.g. `interactive_workload`'s menu
selection); the rest is a thin wrapper around these tested functions.

## Windows notes

- Works with the standard Windows Python installer — no extra dependencies.
- GPU auto-detection shells out to `nvidia-smi`, which is included with
  NVIDIA's Windows driver package and is normally already on `PATH`. If it
  isn't found, the script says so and falls back to asking for GPU specs
  manually.
- The optional local-endpoint benchmark works the same way on Windows as
  elsewhere — point it at `http://localhost:11434` for a local Ollama
  install, or your OpenAI-compatible server's base URL.
