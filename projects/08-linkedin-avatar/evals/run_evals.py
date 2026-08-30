"""Behavioural eval harness — question in, assertion on behaviour out.

Run manually before each deploy; not wired into CI (it costs money and
needs DEEPSEEK_API_KEY). Every assertion targets behaviour, not exact
wording — see docs/design.md §8 and evals/cases.yaml.

Usage:
    python evals/run_evals.py
    python evals/run_evals.py --model deepseek-v4-pro
"""

import argparse
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from avatar import context, guardrails, llm, tools  # noqa: E402

CASES_PATH = Path(__file__).parent / "cases.yaml"


def load_cases(path=CASES_PATH):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run_case(case, system_prompt):
    """Run one case against the real API, with tools.dispatch spied on
    (to see which tools fired) and every notification channel stubbed via
    tools._notify (so nothing real is ever sent, regardless of what's in
    the environment or how many channels are configured)."""
    calls = []
    real_dispatch = tools.dispatch

    def spy_dispatch(name, arguments):
        calls.append(name)
        return real_dispatch(name, arguments)

    with patch.object(tools, "_notify", return_value={"status": "stubbed", "channels": {}}):
        with patch.object(tools, "dispatch", side_effect=spy_dispatch):
            reply, usage = llm.send_message(
                [{"role": "user", "content": case["question"]}], system_prompt
            )

    failures = []

    expected_tool = case.get("expect_tool_call")
    if expected_tool and expected_tool not in calls:
        failures.append(f"expected tool call {expected_tool!r}, got {calls}")

    for substring in case.get("expect_substrings", []):
        if substring.lower() not in reply.lower():
            failures.append(f"missing expected substring: {substring!r}")

    any_of = case.get("expect_any_substrings")
    if any_of and not any(s.lower() in reply.lower() for s in any_of):
        failures.append(f"expected at least one of {any_of!r}, found none")

    for substring in case.get("forbid_substrings", []):
        if substring.lower() in reply.lower():
            failures.append(f"contains forbidden substring: {substring!r}")

    for pattern in case.get("forbid_regex", []):
        if re.search(pattern, reply):
            failures.append(f"matched forbidden pattern: {pattern!r}")

    return {
        "name": case["name"],
        "reply": reply,
        "tool_calls": calls,
        "usage": usage,
        "passed": not failures,
        "failures": failures,
    }


def print_report(results, model):
    name_width = max(len(r["name"]) for r in results) + 2
    print(f"{'CASE':<{name_width}}RESULT")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{r['name']:<{name_width}}{status}")
        for failure in r["failures"]:
            print(f"    - {failure}")

    passed = sum(1 for r in results if r["passed"])
    total_cost = sum(guardrails.estimate_cost_usd(r["usage"], model) for r in results)
    print(
        f"\n{passed}/{len(results)} passed. Estimated cost: ${total_cost:.4f} (model={model})"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default=None, help="Override AVATAR_MODEL for this run"
    )
    parser.add_argument("--cases", default=str(CASES_PATH))
    args = parser.parse_args(argv)

    model = args.model or os.environ.get("AVATAR_MODEL", llm.DEFAULT_MODEL)
    os.environ["AVATAR_MODEL"] = model

    cases = load_cases(Path(args.cases))
    system_prompt = context.build_system_prompt()

    results = [run_case(case, system_prompt) for case in cases]
    print_report(results, model)

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
