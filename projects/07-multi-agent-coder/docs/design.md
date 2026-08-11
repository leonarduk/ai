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

- **Primary use case: keep coding when cloud token budget is exhausted.**
  This isn't meant to out-perform Claude/DeepSeek with tokens available —
  when those are exhausted, the honest alternative is a single local model
  with no scaffolding at all, and *that's* the bar this needs to clear, not
  a fully-tokened cloud session. See issue #106: validate this against a
  single-model baseline (and against Aider, which already implements the
  execution-feedback loop) before building out the rest of the pipeline.
- Higher-quality patches than a single unreviewed model call: a Coder
  proposes, a Verifier proves (tests/lint), a Reviewer critiques.
- Run entirely on local hardware by default (Ollama); cloud providers
  (DeepSeek, Claude) are opt-in, same informed-consent pattern as
  `05-prize-draw-orchestrator/llm_providers.py`.
- Cheap roles get cheap models, hard roles get strong ones — the same
  `local-7b` / `local-14b` / `haiku` / `sonnet` / `opus` sizing this repo
  already uses to label GitHub issues applies naturally to picking which
  model handles which agent role.
- Use whatever local compute is available across the user's LAN, not just
  the machine running the orchestrator: each agent role can point at an
  Ollama instance on a different PC. One 8GB-GPU box only fits one 14B
  model at a time; a second or third PC each running their own `ollama
  serve` removes that ceiling without needing any cloud provider. See
  'Multiple local PCs' under Architecture.
- Every milestone is a working CLI tool, not a service that needs the next
  milestone to be useful.

## Non-goals (for now)

- Running our *own* agent code (not just the LLM call) on a second
  machine — i.e. an actual Coder/Reviewer/Verifier process listening on a
  network port, per the original spec's orchestrator/agent-service split —
  deferred to the M3 stretch milestone. This is a different, harder problem
  than pointing a role at a remote Ollama host: it means designing a wire
  protocol, handling partial failures across machines, etc. Nothing here
  blocks using multiple PCs for their Ollama models today (see Goals).
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

M2 inserts a Reviewer pass between Coder and Verifier. The pipeline itself
stays a single Python process throughout M1/M2 — what can already be
distributed across machines starting in M2 is which Ollama instance each
role's *model* calls hit (see 'Multiple local PCs' below), which needs no
networking code of our own since Ollama already serves its API over the
LAN. M3 (stretch) is the only milestone that runs our own agent *code* on
a second machine — the original spec's orchestrator/agent-service split,
attempted last instead of first.

### Multiple local PCs

Ollama already listens on the network when started with
`OLLAMA_HOST=0.0.0.0 ollama serve` (or the Windows service equivalent), so
using a second or third PC's model doesn't need any code beyond pointing
`OllamaProvider.host` at that machine's address instead of `localhost`.
`config.py` gives each role its own host, not just its own model:

```
CODER_OLLAMA_HOST=http://pc-a.local:11434
CODER_MODEL=qwen2.5-coder:14b-instruct-q4_K_M

REVIEWER_OLLAMA_HOST=http://pc-b.local:11434
REVIEWER_MODEL=qwen2.5-coder:7b-instruct-q4_K_M
```

Each PC still only fits one resident 14B model at a time (see
[`docs/ollama_setup_guide.md`](../../../docs/ollama_setup_guide.md)), so
this is what actually lifts that per-machine ceiling — Coder and Reviewer
can now run on different GPUs instead of time-sharing one. Two things this
still doesn't need: our own network protocol (Ollama's HTTP API is the
transport) or the M3 remote-agent work (the *Python logic* for each role
still runs on the orchestrator's machine; only the model inference call
crosses the network). Per-role timeouts should be generous and
independently configurable — a LAN PC under load or asleep is a more likely
failure mode than `localhost`, and the existing `OllamaProvider` error
message ("Is `ollama serve` running?") should be extended to suggest
checking network reachability too.

### Components

- **`llm_client.py`** — generalises `05-prize-draw-orchestrator/llm_providers.py`'s
  `LLMProvider` protocol from `generate_json` to a `chat(messages) -> str`
  call (agents need free-text diffs and review prose, not just JSON), plus a
  `generate_json` passthrough for structured results (test-result summaries,
  risk level). Same three backends: `OllamaProvider` (default, local-only),
  `DeepSeekProvider`, `ClaudeProvider`.
- **`config.py`** — per-role model/provider/host selection (`CODER_MODEL`,
  `CODER_OLLAMA_HOST`, `REVIEWER_MODEL`, `REVIEWER_OLLAMA_HOST`, etc.),
  workspace root, test/lint command — same shape as
  `05-prize-draw-orchestrator/config.py`, extended with the per-role host so
  roles can be pinned to different PCs (see 'Multiple local PCs').
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

**M2 — Reviewer + multi-provider + multi-PC + history.** Adds the Reviewer
role, per-role model/provider/host config (including opt-in DeepSeek/Claude
and pointing individual roles at Ollama instances on other LAN PCs), SQLite
run history, and a risk-level summary in the CLI output.

**M3 — Stretch: remote agent processes + dashboard.** Only if M1/M2 prove
useful in practice. Unlike M2's multi-PC support (routing a role's *model*
calls to another machine, no new networking code), this is about running
our own Coder/Reviewer/Verifier *code* on a second machine — a minimal HTTP
boundary (FastAPI) between orchestrator and agent process, the original
spec's actual architecture. Also in scope here: a read-only dashboard over
the SQLite history; a VS Code integration spike (not a committed
deliverable); and giving the Coder/Reviewer an MCP doc-lookup tool (e.g.
Context7, same idea as `engineering_team`'s design-lead agent) so they can
check current library APIs instead of relying on training-data recall —
directly targets the "reduce hallucinated API calls" goal, which nothing in
M1/M2 actually addresses yet. Stretch-tier because it depends on this
repo's MCP tool access being wired up for a standalone script, not just for
editor/agent sessions.

## Open questions

- Diff format robustness: local 7B/14B models are inconsistent at emitting
  clean unified diffs. M1's Coder issue should budget time for prompt
  iteration and a fallback (e.g. full-file rewrite for small files) before
  assuming diff application will just work.
- Revision loop bound: needs a default (e.g. 3 attempts) exposed via config,
  not hardcoded, so it can be tuned per task difficulty.
