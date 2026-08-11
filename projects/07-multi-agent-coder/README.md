# Multi-Agent Coder

A small multi-agent pipeline that splits coding work across specialised
LLM roles — Coder, Reviewer, Verifier — instead of relying on one model to
generate, judge, and prove its own patch. Runs locally against Ollama by
default; DeepSeek/Claude are opt-in.

**Status:** design stage — see [`docs/design.md`](./docs/design.md) for the
full architecture, milestones, and the reasoning behind scaling down the
original multi-PC spec to a single-process CLI first.

## Why

A single local model asked to "fix this bug" tends to hallucinate APIs and
miss its own mistakes. Splitting the work — one pass to generate a patch,
one to run the tests, one to critique before it ships — catches more than
asking the same model to do all three in one shot, the same way code review
catches things self-review doesn't.

## Planned usage (M1)

```bash
multiagent-coder run --task "Fix null pointer in UserService" --files src/UserService.py
```

Produces a unified diff, applies it in a scratch git branch, runs the
project's tests, and reports pass/fail — retrying with the Coder for a
bounded number of revisions on failure.

## Status

Not yet implemented — tracked as GitHub issues under the `Multi-Agent
Coder — M1: Single-process MVP` milestone. See
[`docs/design.md`](./docs/design.md) for the roadmap.
