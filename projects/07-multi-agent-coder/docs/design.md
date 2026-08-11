# Multi-Agent Coder — Design Doc

## Origin

A Copilot-authored spec proposed a networked multi-PC system: an
orchestrator service plus Coder/Reviewer/Verifier agents each on their own
machine, talking over HTTP/gRPC, backed by Postgres/Redis, with a CLI, a web
UI, and a VS Code extension. That's a reasonable shape for a funded team
project. It's the wrong shape for this repo: one developer, one machine with
a single 8GB-VRAM GPU that fits one 14B model at a time (see
[`docs/ollama_setup_guide.md`](../../../docs/ollama_setup_guide.md)), and a
track record ([`05-prize-draw-orchestrator`](../05-prize-draw-orchestrator))
of flat, single-process Python modules with a `LLMProvider` abstraction, a
`cli.py` entrypoint, and per-project `requirements.txt` + `tests/`.

This doc keeps the original idea — specialised agents catch more than one
generalist model — but sequences it so each milestone ships something
runnable, starting from a single process before any networking exists.

## Alternatives considered

[ed-donner/agents' `engineering_team` example](https://github.com/ed-donner/agents/tree/main/3_crewai/reference/engineering_team)
does something structurally similar (Lead/Backend/Frontend/Test agents,
sequential pipeline, one model per role) on top of CrewAI — YAML-configured
agents/tasks, built-in tracing, task-dependency wiring via `context:`.
Considered and rejected as the framework for this project:

- Every existing project in this repo (`05-prize-draw-orchestrator` in
  particular) is a hand-rolled `LLMProvider`/`cli.py`/flat-module setup with
  no agent-orchestration framework. Adopting CrewAI here would make this the
  one project with a fundamentally different dependency shape and mental
  model from everything else in `projects/`, for a pipeline that's simple
  enough (Coder → Reviewer → Verifier, sequential, three roles) not to need
  it.
- CrewAI's value — YAML-declared agents/tasks, hierarchical process,
  built-in tracing — pays off more as team size and task-graph complexity
  grow. M1/M2 here are a fixed three/four-role sequential pipeline; a
  framework built for arbitrary crews is overhead until (if ever) the
  pipeline actually needs that flexibility.

Their agent/task split is also solving a different problem — decomposing a
*greenfield app build from requirements* (design → backend → frontend →
tests) — versus this project's *patch an existing repo* (bugfix/feature/
refactor), so the role split doesn't transfer directly. What does transfer:
their sandbox-tool design (see `workspace.py` below) and their use of an
MCP doc-lookup tool to cut hallucinated APIs (see M3).

## Goals

- Higher-quality patches than a single unreviewed model call: a Coder
  proposes, a Verifier proves (tests/lint), a Reviewer critiques.
- Run entirely on local hardware by default (Ollama); cloud providers
  (DeepSeek, Claude) are opt-in, same informed-consent pattern as
  `05-prize-draw-orchestrator/llm_providers.py`.
- Cheap roles get cheap models, hard roles get strong ones — the same
  `local-7b` / `local-14b` / `haiku` / `sonnet` / `opus` sizing this repo
  already uses to label GitHub issues applies naturally to picking which
  model handles which agent role.
- Every milestone is a working CLI tool, not a service that needs the next
  milestone to be useful.

## Non-goals (for now)

- Multi-PC networked deployment — deferred to a stretch milestone. One
  8GB-GPU machine can't run Coder + Reviewer concurrently anyway; the
  pipeline is sequential by construction, so a second machine buys nothing
  until agents actually need to overlap.
- Postgres/Redis — SQLite is enough for one user's task history.
- VS Code extension / production web UI — spike only, if time allows.

## Architecture (MVP → stretch)

A single Python process, one pipeline, run from a CLI:

```
task description + target files
        │
        ▼
   ┌─────────┐   unified diff    ┌──────────┐   pass/fail + output   ┌──────────┐
   │  Coder  │ ────────────────► │ Verifier │ ─────────────────────► │  result  │
   └─────────┘                   └──────────┘                        └──────────┘
        ▲                             │ fail (bounded retries)
        └─────────────────────────────┘
```

M2 inserts a Reviewer pass between Coder and Verifier. M3 (stretch) is the
only milestone that touches networking, and only to let Reviewer/Verifier
run on a second machine — the original spec's idea, attempted last instead
of first.

### Components

- **`llm_client.py`** — generalises `05-prize-draw-orchestrator/llm_providers.py`'s
  `LLMProvider` protocol from `generate_json` to a `chat(messages) -> str`
  call (agents need free-text diffs and review prose, not just JSON), plus a
  `generate_json` passthrough for structured results (test-result summaries,
  risk level). Same three backends: `OllamaProvider` (default, local-only),
  `DeepSeekProvider`, `ClaudeProvider`.
- **`config.py`** — per-role model/provider selection (`CODER_MODEL`,
  `REVIEWER_MODEL`, etc.), workspace root, test/lint command — same shape as
  `05-prize-draw-orchestrator/config.py`.
- **`agents/coder.py`** — builds a prompt from task description + file
  contents, asks the LLM for a unified diff + explanation.
- **`agents/reviewer.py`** (M2) — reviews a diff for correctness/API misuse/
  style, returns structured comments + a risk level.
- **`workspace.py`** — applies a diff inside a scratch git branch/worktree,
  runs the configured test/lint command, reports pass/fail, rolls back on
  failure. No LLM involved.

  Diff application is the least reliable part of this loop (see 'Open
  questions'). `ed-donner/agents`' `engineering_team` example sidesteps the
  problem entirely: its agents get flat `list/read/write/run` sandbox tools
  and the Coder just writes whole files, no diff involved. We can't fully
  adopt that — we're patching an existing repo, not writing into a fresh
  scratch directory, so the git-branch isolation stays — but the same
  full-file-write fallback belongs in `workspace.py`: for files under a
  size threshold, let the Coder return complete file contents instead of a
  diff, write them directly inside the scratch branch, and let `git diff`
  show the resulting change. Reserve unified-diff parsing for files too
  large to round-trip whole.
- **`orchestrator.py`** — runs Coder → (Reviewer) → Verifier, loops back to
  Coder with the failure output for a bounded number of revisions, returns a
  final bundle (patch, review summary, test status, risk level).
- **`cli.py`** — `multiagent-coder run --task "..." --files a.py b.py`.
- **`history.py`** (M2) — SQLite log of each run: task, patches attempted,
  review comments, test results, so past runs are inspectable.

### Repo layout

```
projects/07-multi-agent-coder/
  README.md
  requirements.txt
  config.py
  cli.py
  llm_client.py
  workspace.py
  orchestrator.py
  history.py                # M2
  agents/
    coder.py
    reviewer.py              # M2
  docs/
    design.md                # this file
  tests/
    test_llm_client.py
    test_workspace.py
    test_orchestrator.py
    ...
```

Matches the CI convention in `.github/workflows/python-ci.yml`: it
auto-discovers any `projects/*/tests/` directory and installs the nearest
`requirements.txt`, so no CI changes are needed to onboard this project.

## Data model (MVP)

```python
@dataclass
class AgentResult:
    role: str                 # "coder" | "reviewer" | "verifier"
    output: str                # diff, review text, or test output
    passed: bool | None = None # verifier only
    confidence: float | None = None

@dataclass
class TaskRun:
    task_id: str
    description: str
    files: list[str]
    attempts: list[AgentResult]
    status: str                 # "completed" | "failed" | "aborted"
    final_diff: str | None
```

Full `Task`/`AgentRequest`/`AgentResponse`/`Patch` types from the original
spec are still the right shape for M3, once there's an HTTP boundary between
processes that needs a wire format. Before that boundary exists they'd just
be dataclasses talking to themselves — pushed out until M3 designs the API.

## Milestones

**M1 — Single-process MVP.** Coder → Verifier loop, Ollama only, CLI. A
patch either passes tests within N revisions or the run reports failure with
the last diff and test output.

**M2 — Reviewer + multi-provider + history.** Adds the Reviewer role,
per-role model/provider config (including opt-in DeepSeek/Claude), SQLite
run history, and a risk-level summary in the CLI output.

**M3 — Stretch: remote agents + dashboard.** Only if M1/M2 prove useful in
practice. A minimal HTTP boundary (FastAPI) so Reviewer/Verifier can run on
a second machine, plus a read-only dashboard over the SQLite history. VS
Code integration is a spike, not a committed deliverable. Also: give the
Coder/Reviewer an MCP doc-lookup tool (e.g. Context7, same idea as
`engineering_team`'s design-lead agent) so they can check current library
APIs instead of relying on training-data recall — directly targets the
"reduce hallucinated API calls" goal, which nothing in M1/M2 actually
addresses yet. Stretch-tier because it depends on this repo's MCP tool
access being wired up for a standalone script, not just for editor/agent
sessions.

## Open questions

- Diff format robustness: local 7B/14B models are inconsistent at emitting
  clean unified diffs. M1's Coder issue should budget time for prompt
  iteration and a fallback (e.g. full-file rewrite for small files) before
  assuming diff application will just work.
- Revision loop bound: needs a default (e.g. 3 attempts) exposed via config,
  not hardcoded, so it can be tuned per task difficulty.
