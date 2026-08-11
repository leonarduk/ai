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

The shape below has moved twice since the first draft of this doc:

1. First cut: a single CLI-triggered pipeline (Coder → Reviewer → Verifier),
   run once per `multiagent-coder run --task "..."` invocation.
2. Current cut: **GitHub issues are the queue.** A Triage step reads an
   issue, checks it's actually scoped (asking clarifying questions if not),
   and labels it `Ready`. A Scheduler dispatches `Ready` issues to whichever
   local Coder capacity is free. Coder → Verifier run as before, but a
   failed Verifier run goes to an **Analyser** — not a pre-test Reviewer —
   which reads the actual failure output and tells the Coder what to try
   next. A passing run opens a PR.

This is a better fit for this repo than the original CLI-only version: it
extends a pattern the repo already uses (`cicaid`'s issue/label-driven
automation — `triage-issues`, `sync-issues`, labels like `ai-suggested`)
rather than inventing a parallel one, and it replaces a *speculative*
pre-test critique role with a *targeted* post-failure one — reacting to
concrete test output is the well-evidenced half of these loops, not
free-form code review before anything's been run.

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
  model from everything else in `projects/`.
- CrewAI's value — YAML-declared agents/tasks, hierarchical process,
  built-in tracing — pays off more as team size and task-graph complexity
  grow. This pipeline is a fixed handful of sequential roles; a framework
  built for arbitrary crews is overhead until (if ever) it actually needs
  that flexibility.

Their agent/task split is also solving a different problem — decomposing a
*greenfield app build from requirements* — versus this project's *patch an
existing repo from a GitHub issue*, so the role split doesn't transfer
directly. What does transfer: their sandbox-tool design (see 'Pluggable
Coder backends' below) and their use of an MCP doc-lookup tool to cut
hallucinated APIs (see M3).

### Comparison to Aider

The more relevant "why not just use an existing tool" question is Aider,
not CrewAI — it's a single CLI against one model, and it already
implements the highest-leverage piece of this design:

- **Aider already has an execution-feedback loop** (`--auto-test`): it runs
  your tests after an edit and feeds failures back to the model. That's
  this project's Coder → Verifier → Analyser loop, shipped and
  battle-tested for the Coder-only version of it. We are not claiming to
  beat that outright — issue #106 benchmarks our loop against Aider on the
  same tasks specifically because Aider is the bar to clear, not a
  strawman.
- **Aider already supports a two-model split** (architect/editor). What
  Aider doesn't have: an issue-driven queue with a readiness gate, a
  Scheduler that dispatches across multiple LAN machines, a distinct
  post-failure Analyser pass, or an automatic PR at the end.
- Aider isn't purely an external comparison point, either: it's pluggable
  *as* this project's Coder backend (see 'Pluggable Coder backends'), so we
  don't have to re-solve diff/edit-format reliability ourselves.
- **Why build this instead of just using Aider directly:** per the Goals
  section, the reason isn't "better than Aider at editing" — it's needing
  something that runs unattended against a backlog of GitHub issues, across
  multiple local models and multiple LAN machines, once cloud tokens (and
  Aider's own interactive-session model) are no longer the plan.

## Goals

- **Primary use case: keep coding when cloud token budget is exhausted.**
  This isn't meant to out-perform Claude/DeepSeek with tokens available —
  the bar is a single unassisted local model, since that's the honest
  alternative once tokens run out. See issue #106: validate the core loop
  against that baseline (and against Aider) before building the rest.
- **Unattended, issue-driven operation.** You file (or already have) a
  GitHub issue; the system decides for itself whether it's ready to act on,
  asks if it isn't, and opens a PR if it succeeds — without you sitting at
  a CLI feeding it a `--task` string per attempt.
- Higher-quality patches than a single unreviewed model call, via
  execution feedback: Coder proposes, Verifier proves (tests/lint), and on
  failure Analyser tells Coder specifically what to fix, not just "it
  failed."
- Run entirely on local hardware by default (Ollama); cloud providers
  (DeepSeek, Claude) are opt-in, same informed-consent pattern as
  `05-prize-draw-orchestrator/llm_providers.py`.
- Cheap roles get cheap models, hard roles get strong ones — the same
  `local-7b` / `local-14b` / `haiku` / `sonnet` / `opus` sizing this repo
  already uses to label GitHub issues applies naturally to picking which
  model handles which agent role.
- Use whatever local compute is available across the user's LAN: the
  Scheduler dispatches work to whichever configured PC's Ollama instance is
  free, not just the machine running the orchestrator. One 8GB-GPU box only
  fits one 14B model at a time; a second or third PC removes that ceiling
  without needing any cloud provider.
- Every milestone is a working, independently useful piece — M1's CLI loop
  works stand-alone before M2 wraps it in the issue-driven pipeline.

## Non-goals (for now)

- **Auto-merging.** This pipeline opens a PR on success; it does not merge
  it. This repo already runs automated PR review (Claude/DeepSeek/GPT
  advisory reviews per `CONTRIBUTING.md`) — those inform a human merge
  decision, they aren't a green light for this tool to merge itself.
- Running our *own* agent code (not just the LLM call) on a second
  machine — i.e. an actual Coder/Verifier/Analyser process listening on a
  network port — deferred to the M3 stretch milestone. Different, harder
  problem than the Scheduler dispatching model calls to a remote Ollama
  host: it means a wire protocol, health checks, partial-failure handling
  across machines.
- Postgres/Redis — SQLite is enough for one user's task history.
- VS Code extension / production web UI — spike only, if time allows.

## Architecture

```
GitHub issue
     │
     ▼
 ┌─────────┐  underspecified   ┌────────────────────────┐
 │ Triage  │ ────────────────► │ comment + needs-info    │──┐
 └─────────┘                   └────────────────────────┘  │ user replies
     │ scoped                                               │
     ▼                                                       │
 label: Ready ◄───────────────────────────────────────────────┘
     │
     ▼
 ┌───────────┐   dispatch to free    ┌─────────┐  diff   ┌──────────┐
 │ Scheduler │ ─────────────────────►│  Coder  │ ───────►│ Verifier │
 └───────────┘   Coder capacity      └─────────┘         └──────────┘
                       ▲                                    │      │
                       │        instructions           fail │      │ pass
                       │  ┌──────────┐                       ▼      ▼
                       └──┤ Analyser │◄───────────── test/lint   open PR
                          └──────────┘   output      output
                     (bounded revisions)
```

M1 builds the inner loop (Coder → Verifier → Analyser) as a CLI tool driven
by `--task`, so it's cheap to benchmark (#106) before investing in the
outer loop. M2 wraps it: Triage, the `Ready` label, the Scheduler, and the
PR step turn the CLI tool into something that runs against a real issue
backlog unattended. M3 is the only milestone that runs our own agent *code*
(not just a model call) on a second machine.

**M2 vs M3, at a glance — two different things both called "remote":**

| | What crosses the network | New code required | Milestone |
|---|---|---|---|
| Remote **model** (Scheduler dispatch) | One `chat()` call's prompt/response | None — Ollama already serves HTTP | M2 |
| Remote **agent** | The role's whole Python process (prompt-building, retries, tool calls) | A wire protocol (FastAPI), health checks, partial-failure handling | M3 |

### Triage

Reads the issue body/comments and the repo, and decides one of two things:

- **Underspecified** — post a comment naming what's missing (which
  file(s)? what's the expected behaviour? is there a failing test to
  reproduce?), label `needs-info`, and stop. The Scheduler skips
  `needs-info` issues. Triage re-runs on its next pass over open issues
  (not on a reply webhook — this repo has no always-on service, so
  "wait for reply" means "check again next time Triage runs") and re-labels
  `Ready` once the new comments answer its questions, or leaves
  `needs-info` if they don't.
- **Scoped** — write a short scoping note as an issue comment (which
  files it expects to touch, what "done" looks like) and label `Ready`.
  This is deliberately similar to what a human would do before picking up
  a ticket; it's also what `agents/coder.py`'s `task` input is built from,
  so a well-scoped comment here directly improves Coder's odds.

Triage never edits code or opens a scratch branch — it only reads the repo
to judge scope, the same read-only relationship this project's own `Explore`-
style research has to a codebase.

### Scheduler

Polls open issues for the `Ready` label (not a webhook — same reasoning as
Triage: no always-on service to receive one). For each `Ready` issue not
already claimed:

1. Claim it: add an `in-progress` label. Single Scheduler process, so this
   isn't a distributed race — but if the process crashes mid-run, the
   `in-progress` label (not in-memory state) is what a restarted Scheduler
   uses to recover what was already claimed.
2. Pick a free Coder target from the configured pool — a local Ollama
   host, or a cloud provider role, per `config.py` (see 'Pluggable Coder
   backends' and 'Configured Coder targets' below).
3. Run the Coder → Verifier → Analyser loop against that target.
4. On success: push the scratch branch, open a PR, remove `in-progress`,
   add e.g. `pr-opened`. On exhausting the revision bound: comment the
   failure summary (last diff, last test output) on the issue, remove
   `in-progress`, add e.g. `needs-help` so it's visibly distinct from
   `Ready` (still unsolved) and from `needs-info` (Triage's concern, not
   the Coder's).

This is what "use multiple local PCs" actually needed — not just a static
per-role host in config (the earlier version of this doc), but something
that knows which hosts are currently free and dispatches accordingly.

### Analyser

Runs only after a Verifier failure — never before a patch has actually
been tested. Given the failing diff, the raw test/lint output, and which
revision attempt this is, it produces concrete instructions for the next
Coder attempt: which assertion/error to address, whether the previous
diff's approach looks fundamentally wrong (suggest a different approach)
or just incomplete (suggest a specific fix), and whether the failure looks
like a bad diff apply rather than a real test failure (see the malformed-
diff detection under `workspace.py`). This replaces the earlier draft's
pre-test "Reviewer" role: reacting to concrete failure output is the part
of these loops with real evidence behind it; free-form critique of a diff
that hasn't been run yet is the part #106 was skeptical of, and the user's
actual workflow never called for it — so it's cut, not deferred.

### Pluggable Coder backends

`agents/coder.py` defines a `Coder` protocol — `propose(workspace_dir,
task, files) -> str` (a unified diff or full-file content, see below) —
with two implementations, selected via `CODER_BACKEND=native|aider`:

- **`NativeCoder`** (default) — prompts the configured model directly,
  returns a diff or full-file body per the size-threshold rule below.
- **`AiderCoder`** — shells out to `aider --yes --no-auto-commits
  --message "<task>" <files>` inside the scratch branch/worktree that
  `workspace.py` already prepared, then reads the result back via `git
  diff` rather than parsing Aider's own output. `--no-auto-commits`
  matters because Aider commits directly to the current branch by default,
  which would fight the scratch-branch isolation model — we want Aider's
  edits sitting as uncommitted changes, exactly like `NativeCoder`'s
  output, so the Scheduler/Analyser/history don't need to know which
  backend ran.

Both backends produce the same thing from `workspace.py`'s perspective — a
diff sitting in the scratch branch — so Verifier, Analyser, the revision
loop, and the Scheduler are entirely backend-agnostic. `CODER_BACKEND` is
also a benchmark parameter: #106's "Aider standalone" arm and this
project's own loop can share one harness.

Coupling to Aider's CLI is a real dependency risk: pin a tested version in
`requirements.txt` rather than floating on latest, and treat an Aider
upgrade as a change that needs re-testing `AiderCoder`, not a routine bump.

### Configured Coder targets (multiple local PCs)

Ollama already listens on the network when started with
`OLLAMA_HOST=0.0.0.0 ollama serve` (or the Windows service equivalent), so
using a second or third PC's model doesn't need any code of our own beyond
pointing `OllamaProvider.host` at that machine's address. `config.py`
declares the pool the Scheduler picks from:

```
CODER_TARGETS=
  pc-a: http://pc-a.local:11434, qwen2.5-coder:14b-instruct-q4_K_M
  pc-b: http://pc-b.local:11434, qwen2.5-coder:7b-instruct-q4_K_M

ANALYSER_MODEL=qwen2.5-coder:7b-instruct-q4_K_M
ANALYSER_OLLAMA_HOST=http://pc-b.local:11434
```

Each PC still only fits one resident 14B model at a time, so this is what
actually lifts that per-machine ceiling — a second `Ready` issue can be
dispatched to `pc-b` while `pc-a` is still working the first. Per-target
timeouts should be generous and independently configurable — a LAN PC
under load or asleep is a more likely failure mode than `localhost` — and
the Scheduler should mark a target unavailable (not retry it immediately)
after a reachability failure, re-checking on a later pass.

### Components

- **`llm_client.py`** — generalises `05-prize-draw-orchestrator/llm_providers.py`'s
  `LLMProvider` protocol from `generate_json` to a `chat(messages) -> str`
  call, plus a `generate_json` passthrough for structured results
  (Analyser's next-step instructions, Triage's ready/not-ready verdict).
  Same three backends: `OllamaProvider` (default, local-only),
  `DeepSeekProvider`, `ClaudeProvider`.
- **`config.py`** — per-role model/provider selection, the `CODER_TARGETS`
  pool, workspace root, test/lint command — same shape as
  `05-prize-draw-orchestrator/config.py`, extended for the target pool.
- **`triage.py`** — reads an issue + repo, posts a comment and labels
  `needs-info` or `Ready` (see 'Triage' above).
- **`scheduler.py`** — polls for `Ready` issues, claims and dispatches them
  across `CODER_TARGETS`, opens the PR or posts the failure comment (see
  'Scheduler' above).
- **`agents/coder.py`** — defines the `Coder` protocol and `NativeCoder`.
- **`agents/coder_aider.py`** — `AiderCoder`, the Aider-backed
  implementation of the same protocol.
- **`agents/analyser.py`** — reads a failed Verifier result and produces
  the next Coder attempt's instructions (see 'Analyser' above).
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
  hundred lines) in the #93 implementation and adjust from real failures.

  A diff is malformed, not just "the model was wrong," when it fails to
  parse as unified-diff syntax, references line numbers or context that
  don't match the target file, or touches a file outside the task's
  declared file list. `workspace.py` should detect these *before* handing
  anything to `git apply` and the failure reason — not just "failed" — is
  part of what Analyser sees for the next revision.
- **`orchestrator.py`** — runs Coder → Verifier, and on failure hands the
  result to Analyser before looping back to Coder, up to a bounded number
  of revisions. Returns a final bundle (patch, test status, attempt
  history). Used directly by `cli.py` (M1) and by `scheduler.py` (M2) —
  the loop itself doesn't know whether it was triggered by a CLI flag or a
  dispatched issue.
- **`cli.py`** — `multiagent-coder run --task "..." --files a.py b.py`
  (M1) for driving the core loop directly, without the issue-driven
  wrapper — this is what #106's benchmark uses.
- **`history.py`** — SQLite log of each run: source (CLI task or issue
  number), patches attempted, Analyser instructions, test results, final
  outcome (PR opened / needs-help / needs-info), so past runs are
  inspectable via `multiagent-coder history`.

### Revision loop feedback signals

On a failed Verifier run, `orchestrator.py` feeds back to the next Coder
attempt:

- The **raw test/lint output** from the Verifier, unmodified.
- The **diff-application failure reason**, if the previous attempt's diff
  didn't apply cleanly — distinct from a test failure, since it means the
  Coder's patch was never actually tried.
- **Analyser's instructions**, derived from the above — which specific
  thing to fix, and whether the previous approach looks salvageable or
  needs rethinking. Whether Analyser's added signal measurably beats
  raw Verifier output alone is exactly what #106 (or a follow-up rerun of
  it once Analyser exists) should answer.

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
  triage.py                 # M2
  scheduler.py               # M2
  history.py
  agents/
    coder.py                 # Coder protocol + NativeCoder
    coder_aider.py            # AiderCoder backend
    analyser.py               # post-failure feedback
  docs/
    design.md                # this file
  tests/
    test_llm_client.py
    test_workspace.py
    test_orchestrator.py
    test_triage.py            # M2
    test_scheduler.py          # M2
    ...
```

Matches the CI convention in `.github/workflows/python-ci.yml`: it
auto-discovers any `projects/*/tests/` directory and installs the nearest
`requirements.txt`, so no CI changes are needed to onboard this project.

## Data model

```python
@dataclass
class AgentResult:
    role: str                 # "coder" | "verifier" | "analyser"
    output: str                # diff, test output, or analyser instructions
    passed: bool | None = None # verifier only
    confidence: float | None = None

@dataclass
class TaskRun:
    task_id: str                # CLI-generated id, or "issue-<number>"
    source: str                  # "cli" | "github-issue"
    description: str
    files: list[str]
    attempts: list[AgentResult]
    status: str                 # "completed" | "failed" | "aborted"
    final_diff: str | None
    pr_url: str | None = None    # set once a PR is opened (M2)
```

Full `Task`/`AgentRequest`/`AgentResponse`/`Patch` types from the original
spec are still the right shape for M3, once there's an HTTP boundary
between processes that needs a wire format. Before that boundary exists
they'd just be dataclasses talking to themselves — pushed out until M3
designs the API.

## Milestones

**M1 — Core loop (CLI-driven).** Coder → Verifier → Analyser-on-failure,
bounded revisions, `CODER_BACKEND=native|aider`, run via
`multiagent-coder run --task "..." --files a.py b.py`. No GitHub
integration yet — this is deliberately the cheapest version to benchmark.

- **Done when:** issue #106's benchmark has run and its result is written
  up — M1 isn't "done" just because the code works, it's done when we know
  whether the loop is worth wrapping in M2's issue-driven pipeline. If
  #106 shows no measurable lift over a single unassisted local model, M1's
  remaining scope is a stopping point to reassess, not a green light to
  keep building.
  - `multiagent-coder run` produces either a passing patch within the
    revision bound, or a clear failure report (last diff, last test
    output, which attempt it stopped at).
  - `pytest projects/07-multi-agent-coder` passes, including
    rollback-path coverage for `workspace.py` and both `CODER_BACKEND`
    values.
  - Ollama unreachable, a malformed diff, and a target file outside the
    task's declared file list all produce a clear CLI error naming the
    cause — never a raw traceback or a silent no-op.

**M2 — Issue-driven pipeline.** Triage (readiness gate + clarifying
questions), the `Ready`/`needs-info`/`in-progress`/`needs-help` label
lifecycle, the Scheduler (dispatch across `CODER_TARGETS`), PR automation
on success, SQLite run history, opt-in DeepSeek/Claude.

- **Done when:** filing (or already having) a well-scoped GitHub issue on
  this repo results in either a draft PR referencing it, or a `needs-help`
  comment with the failure detail, with no manual CLI invocation in
  between; an underspecified issue gets a `needs-info` comment instead of
  being silently skipped or silently attempted; a Scheduler restart
  recovers in-flight state from labels rather than losing track of a
  claimed issue; `multiagent-coder history` lists past runs including
  which issue (if any) triggered them.
- **Open before this is buildable, not yet decided:** does the PR open as
  a draft, or is there a stricter gate before it's real? (This repo's
  existing AI PR-review bots — see `CONTRIBUTING.md` — could serve as that
  gate, or a stricter one may be wanted specifically for auto-opened PRs.)

**M3 — Stretch: remote agent processes + dashboard.** Only if M1/M2 prove
useful in practice. Unlike M2's Scheduler (routing a role's *model* calls
to another machine, no new networking code), this is about running our own
Coder/Verifier/Analyser *code* on a second machine — a minimal HTTP
boundary (FastAPI) between orchestrator and agent process, the original
spec's actual architecture. Also in scope: a read-only dashboard over the
SQLite history; a VS Code integration spike (not a committed deliverable);
and an MCP doc-lookup tool for Coder/Analyser.

The MCP tool (e.g. Context7) would be queried with the library/API name a
patch is about to call, the same way `engineering_team`'s design-lead agent
uses it before writing its design. This slots into `llm_client.py`'s
existing abstraction as an optional tool a role's `chat()` call can invoke
mid-generation, not a new provider. Directly targets the "reduce
hallucinated API calls" goal, which nothing in M1/M2 addresses. Stretch-
tier because it depends on this repo's MCP tool access being usable from a
standalone script/CLI process, not just an interactive agent session.

## Failure modes

- **Model unavailable** (Ollama not running, or a configured target down)
  — `OllamaProvider` should fail fast naming which role's model and host
  it tried, distinguishing "connection refused" from "timeout."
- **LAN PC unreachable** — a specific case of the above: unlike
  `localhost`, a remote PC being asleep or unreachable is an expected
  occasional state, not a bug. The Scheduler should mark that target
  unavailable and try another rather than stalling the whole queue on it.
- **Malformed diffs** — see detection notes under `workspace.py`. Surfaced
  to Analyser as revision feedback first; only surfaced as a `needs-help`
  comment if every revision attempt fails the same way.
- **Tests failing repeatedly** — once the revision bound is hit, stop and
  post the full attempt history as a `needs-help` comment, rather than
  silently leaving the scratch branch's changes anywhere near the user's
  working branch.
- **Workspace corruption** — if `workspace.py` itself errors (scratch
  branch/worktree can't be created or cleaned up), abort the run
  immediately rather than attempting further revisions, and leave enough
  state (branch name, last known-good commit) for manual inspection.
- **Issue never becomes `Ready`** — Triage keeps asking, the user never
  replies (or the issue genuinely can't be scoped). This isn't an error,
  but it's worth the Scheduler surfacing stale `needs-info` issues (e.g.
  no reply after N triage passes) rather than leaving them silently stuck
  forever.
- **Scheduler crash mid-dispatch** — recovery is via labels (`in-progress`
  issues are re-claimed on restart), not in-memory state; see 'Scheduler'
  above. Worth a specific test: kill the Scheduler mid-run and confirm the
  next run picks the issue back up rather than double-dispatching it
  alongside a still-running first attempt.
- **PR push fails** (auth, branch protection, network) — should be
  reported the same way as a Verifier failure (a `needs-help` comment with
  the actual error), not silently dropped after all the revision work
  succeeded.

## Open questions

- Diff format robustness: local 7B/14B models are inconsistent at emitting
  clean unified diffs. M1's Coder issue should budget time for prompt
  iteration and the full-file-write fallback before assuming diff
  application will just work.
- Revision loop bound: needs a default (e.g. 3 attempts) exposed via
  config, tuned using #106's data once Analyser exists.
- Aider version coupling: `AiderCoder` shells out to a CLI whose flags and
  output have changed across releases. Pin a tested version and treat an
  Aider upgrade as a change that needs re-testing, not a routine bump.
- Draft vs. gated PRs (see M2's acceptance criteria) — needs a decision
  before the PR-automation issue can be scoped precisely.
- `needs-info` wait state: re-running Triage on every pass over *all* open
  issues (not just new ones) could get expensive as the backlog grows —
  may need Triage to only re-check `needs-info` issues with new comments
  since its last pass, once there's enough issue volume for it to matter.
