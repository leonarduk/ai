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

### Comparison to Aider

The more relevant "why not just use an existing tool" question is Aider,
not CrewAI — it's a single CLI against one model, and it already
implements the highest-leverage piece of this design:

- **Aider already has an execution-feedback loop** (`--auto-test`): it runs
  your tests after an edit and feeds failures back to the model. That's
  this project's Coder → Verifier loop, shipped and battle-tested. We are
  not claiming to do that better — issue #106 benchmarks our loop against
  Aider on the same tasks specifically because Aider is the bar to clear,
  not a strawman.
- **Aider already supports a two-model split** (architect/editor: one model
  plans, another formats the edit), which is most of what Coder/Verifier
  buys structurally. What Aider doesn't have: a distinct LLM *critique*
  pass (the Reviewer role) — untested value, see #106 — and no built-in way
  to pin different roles to different Ollama hosts on the LAN (see
  'Multiple local PCs').
- **Where the revision loop differs:** Aider's loop is Coder-only —
  test failure text goes straight back to the same model that wrote the
  edit. This project's loop (M2 onward) also inserts Reviewer comments
  into that feedback before the next Coder attempt (see 'Revision loop
  feedback signals' below) — an extra signal Aider's loop doesn't have,
  again unproven until #106 says it helps.
- **Why build this instead of just using Aider:** per the Goals section,
  the actual reason isn't "better than Aider" — it's needing a tool that
  keeps working, unattended, across multiple local models and multiple
  LAN machines, once cloud tokens (and Aider's own cloud-model use) are no
  longer an option.

This is also why Aider isn't purely an external comparison point: it's
pluggable *as* this project's Coder backend (see 'Pluggable Coder
backends' under Architecture), so we don't have to re-solve diff/edit-
format reliability ourselves. #106 still runs Aider standalone as one of
its benchmark arms — that answers "does our Reviewer/scheduling layer add
anything over Aider alone," which is a different question from "which
Coder backend should we default to."

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

**M2 vs M3, at a glance — two different things both called "remote":**

| | What crosses the network | New code required | Milestone |
|---|---|---|---|
| Remote **model** | One `chat()` call's prompt/response | None — Ollama already serves HTTP | M2 |
| Remote **agent** | The role's whole Python process (prompt-building, retries, tool calls) | A wire protocol (FastAPI), health checks, partial-failure handling | M3 |

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

### Pluggable Coder backends

`agents/coder.py` defines a `Coder` protocol — `propose(workspace_dir,
task, files) -> str` (a unified diff or full-file content, see below) —
with two implementations, selected via `CODER_BACKEND=native|aider`:

- **`NativeCoder`** (default) — the LLM-direct approach described
  throughout this doc: prompts the configured model, returns a diff or
  full-file body per the size-threshold rule below.
- **`AiderCoder`** — shells out to `aider --yes --no-auto-commits
  --message "<task>" <files>` inside the scratch branch/worktree that
  `workspace.py` already prepared, then reads the result back via `git
  diff` rather than parsing Aider's own output. `--no-auto-commits`
  matters specifically because Aider commits directly to the current
  branch by default, which would fight our scratch-branch isolation model
  (see `workspace.py` below) — we want Aider's edits sitting as uncommitted
  changes in the scratch branch, exactly like `NativeCoder`'s output, so
  `orchestrator.py` and `history.py` don't need to know which backend ran.

Both backends produce the same thing from `workspace.py`'s perspective — a
diff sitting in the scratch branch — so Reviewer, Verifier, the revision
loop, and multi-PC routing are entirely backend-agnostic. This also means
`CODER_BACKEND` can be a benchmark parameter, not just a runtime choice:
#106's "Aider standalone" arm and this project's "Coder+Verifier" arm can
share the same harness with `CODER_BACKEND=aider` vs `native`, rather than
needing separate integration code for each.

Coupling to Aider's CLI is a real dependency risk worth naming here: Aider
ships fast and its flags/output have changed across versions before.
Shelling out to the CLI (rather than importing its internal Python API) is
the more stable integration point, and `AiderCoder` should pin a tested
Aider version in `requirements.txt` rather than floating on latest.

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
- **`agents/coder.py`** — defines the `Coder` protocol and `NativeCoder`:
  builds a prompt from task description + file contents, asks the LLM for
  a unified diff + explanation.
- **`agents/coder_aider.py`** — `AiderCoder`, the Aider-backed
  implementation of the same protocol (see 'Pluggable Coder backends').
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
  large to round-trip whole. The exact size threshold is a tuning
  parameter, not a design decision — pick a starting value (e.g. a few
  hundred lines) in the #93 implementation and adjust from real failures
  rather than guessing it here.

  A diff is malformed, not just "the model was wrong," when it fails to
  parse as unified-diff syntax, references line numbers or context that
  don't match the target file, or touches a file outside the task's
  declared file list. `workspace.py` should detect these *before* handing
  anything to `git apply` (a hunk-context mismatch should fail fast with a
  clear reason, not surface as a cryptic `git apply` error) and the failure
  reason — not just "failed" — is part of what gets fed back to the Coder
  for the next revision (see below) and shown to the CLI user on final
  failure.
- **`orchestrator.py`** — runs Coder → (Reviewer) → Verifier, loops back to
  Coder with the failure output for a bounded number of revisions, returns a
  final bundle (patch, review summary, test status, risk level).
- **`cli.py`** — `multiagent-coder run --task "..." --files a.py b.py`.
- **`history.py`** (M2) — SQLite log of each run: task, patches attempted,
  review comments, test results, so past runs are inspectable.

### Agent responsibilities (hypotheses, pending #106)

These are starting points for the M1/M2 implementation issues, not settled
requirements — #106 tests whether the Reviewer role earns its place at
all, so treat its bullet as provisional:

- **Coder** must guarantee its output is either a syntactically valid
  unified diff or a complete file body (see the full-file-write fallback
  above) — never prose mixed into the patch — and must restate which
  files it touched so `workspace.py` can reject anything outside the
  task's declared file list before applying it.
- **Reviewer** (M2) checks the diff for API misuse, obvious logic errors,
  and style, and must return a structured risk level (low/medium/high),
  not just free text — the orchestrator needs a value it can act on
  (e.g. surface a warning) without re-parsing prose.
- **Verifier** runs the configured test/lint command and reports a
  structured result — pass/fail, which command ran, and the raw
  stdout/stderr — not an LLM's summary of the output. No model sees test
  output before the Coder does; the Verifier's job is capture, not
  interpretation.

### Revision loop feedback signals

On a failed Verifier run, `orchestrator.py` feeds back to the next Coder
attempt:

- The **raw test/lint output** from the Verifier, unmodified — the Coder
  sees exactly what failed, not a paraphrase.
- The **diff-application failure reason**, if the previous attempt's diff
  didn't apply cleanly (see the malformed-diff detection above) — distinct
  from a test failure, since it means the Coder's patch was never actually
  tried.
- **Reviewer comments** (M2 onward), appended alongside the test output —
  so a revision responds to both "this failed" and "this looks risky."
  Whether this measurably changes outcomes vs. Verifier feedback alone is
  exactly what #106 needs to answer before M2's Reviewer work is treated
  as load-bearing rather than optional.

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
    coder.py                 # Coder protocol + NativeCoder
    coder_aider.py            # AiderCoder backend
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

**M1 — Single-process MVP.** Coder → Verifier loop, Ollama only, CLI.

- **Done when:** issue #106's benchmark has run and its result (whatever it
  is) is written up — M1 isn't "done" just because the code works, it's
  done when we know whether the loop is worth continuing to M2. If #106
  shows no measurable lift over a single unassisted local model, M1's
  remaining scope is a stopping point to reassess, not a green light to
  keep building.
  - `multiagent-coder run --task "..." --files a.py b.py` produces either a
    passing patch within the configured revision bound, or a clear failure
    report (last diff, last test output, which attempt it stopped at).
  - `pytest projects/07-multi-agent-coder` passes, including rollback-path
    coverage for `workspace.py` (apply fails, tests fail, interrupted
    mid-run — see #93).
  - Ollama unreachable, a malformed diff, and a target file outside the
    task's declared file list all produce a clear CLI error naming the
    cause — never a raw traceback or a silent no-op.
  - `CODER_BACKEND=native` and `CODER_BACKEND=aider` both run through the
    same `orchestrator.py`/`workspace.py` path with no backend-specific
    branching outside `agents/coder.py` / `agents/coder_aider.py` — this is
    what lets #106 benchmark them through one harness.

**M2 — Reviewer + multi-provider + multi-PC + history.** Adds the Reviewer
role, per-role model/provider/host config (including opt-in DeepSeek/Claude
and pointing individual roles at Ollama instances on other LAN PCs), SQLite
run history, and a risk-level summary in the CLI output.

- **Done when:** the Reviewer role is justified by #106's data (or a
  follow-up rerun of it with Reviewer included) rather than assumed useful;
  a role can be pointed at a different LAN host via config alone, with a
  reachability failure on that host reported distinctly from a model-error
  failure; `multiagent-coder history` lists past runs from SQLite; DeepSeek/
  Claude remain opt-in with the same informed-consent documentation as
  `05-prize-draw-orchestrator`.

**M3 — Stretch: remote agent processes + dashboard.** Only if M1/M2 prove
useful in practice. Unlike M2's multi-PC support (routing a role's *model*
calls to another machine, no new networking code), this is about running
our own Coder/Reviewer/Verifier *code* on a second machine — a minimal HTTP
boundary (FastAPI) between orchestrator and agent process, the original
spec's actual architecture. Also in scope here: a read-only dashboard over
the SQLite history; a VS Code integration spike (not a committed
deliverable); and an MCP doc-lookup tool for the Coder/Reviewer.

The MCP tool (e.g. Context7) would be queried with the library/API name a
patch is about to call — e.g. before the Coder emits code calling a Gradio
or requests API, it checks the tool for that library's current signature
instead of relying on training-data recall, the same way `engineering_team`'s
design-lead agent uses it before writing its design. This slots into
`llm_client.py`'s existing abstraction as an optional tool the Coder/
Reviewer's `chat()` call can invoke mid-generation, not a new provider —
it augments what a role knows, it doesn't change how its output is
produced or parsed. Directly targets the "reduce hallucinated API calls"
goal, which nothing in M1/M2 actually addresses. Stretch-tier because it
depends on this repo's MCP tool access being usable from a standalone
script/CLI process, not just an interactive agent session — that plumbing
doesn't exist yet and should be scoped as part of #105.

## Failure modes

- **Model unavailable** (Ollama not running, or a remote LAN host down) —
  `OllamaProvider` should fail fast with a message naming which role's
  model and host it tried, distinguishing "connection refused" (nothing
  listening) from "timeout" (something's there but slow/overloaded).
- **LAN PC unreachable** — a specific case of the above worth calling out
  separately: unlike `localhost`, a remote PC being asleep, on a different
  subnet, or blocked by a firewall rule is an expected occasional state,
  not a bug. Per-role timeouts need to be generous enough to not misfire on
  a slow-but-alive remote model, and the error should suggest checking
  reachability (ping/curl the host), not just "is ollama serve running?".
- **Malformed diffs** — see the detection notes under `workspace.py` above.
  Surfaced to the Coder as revision feedback first; only surfaced to the
  CLI user if every revision attempt fails the same way.
- **Tests failing repeatedly** — once the revision bound is hit, stop and
  report failure with the full attempt history, rather than silently
  keeping the last (failing) diff applied. The scratch branch's changes
  should never leak into the user's working branch on a failed run.
- **Workspace corruption** — if `workspace.py` itself errors (e.g. the
  scratch branch/worktree can't be created or cleaned up), that's a harder
  failure than a bad patch: abort the run immediately rather than
  attempting further revisions, and leave enough state (branch name, last
  known-good commit) for the user to inspect or clean up manually.

## Open questions

- Diff format robustness: local 7B/14B models are inconsistent at emitting
  clean unified diffs. M1's Coder issue should budget time for prompt
  iteration and a fallback (e.g. full-file rewrite for small files) before
  assuming diff application will just work.
- Revision loop bound: needs a default (e.g. 3 attempts) exposed via config,
  not hardcoded, so it can be tuned per task difficulty.
- Aider version coupling: `AiderCoder` shells out to a CLI whose flags and
  output have changed across releases. Pin a tested version in
  `requirements.txt` and treat an Aider upgrade as a change that needs
  re-testing `AiderCoder`, not a routine dependency bump.
