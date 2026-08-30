## issue-worm

A multi-agent coder that works GitHub issues end-to-end, using local LLMs via Ollama. It started as
`07-multi-agent-coder` inside this lab and outgrew it enough to become its own repo. It's deliberately
scoped as a fallback for when cloud LLM tokens (Claude, DeepSeek) run out, not a competitor to a
fully-tokened cloud coding session — judge it against "one local model, no scaffolding" as the
baseline, and it earns its complexity by beating that.

## allotmint

My biggest and most active personal project by a distance: a Python/FastAPI investment and portfolio
tracking platform on AWS CDK/Lambda, with thousands of commits and an AI-powered PR review pipeline
(Claude, GPT, DeepSeek) running on every pull request. It's the clearest evidence of what an
AI-directed workflow looks like in practice — I'm mostly directing and reviewing rather than typing,
and the commit history shows it. `allotmint-pro` and `allotmint-mcp` (a standalone MCP server exposing
the platform, including an agentic research tool, to AI clients) sit alongside it.

## cicaid

CLI and automation tooling for AI-assisted GitHub issue and PR workflows — setup, review, and triage.
Built to support the same kind of AI-directed development I use on `allotmint` and this lab, rather
than as a one-off experiment.

## sing-attune

A real-time pitch-tracking practice tool for choir singers: a Windows desktop app (TypeScript/Electron
frontend) that tracks pitch against a MusicXML score using GPU or CPU pitch engines (CUDA/torchcrepe),
streamed over WebSocket. It's the one project here that's nothing to do with finance — a personal
interest (I sing) turned into a real-time systems problem worth solving properly.

## unison

A Java GUI app built for my MSc dissertation: downloads and visualises Usenet (NNTP) discussion
messages, exporting them as Pajek network data for social network analysis. Referenced in the final
chapter of *The SAGE Handbook of Social Network Analysis* (2011) — the oldest project here by a wide
margin, from 2007/2008.

## 01-mcp-server-suite

A collection of MCP servers giving LLMs structured access to external systems — GitHub, filesystem,
git, email, web search — each scoped to one domain rather than one monolithic server. Production-ready
and actively maintained; the design thinking here (independent deployment, clear tool boundaries) is
the same thinking behind the MCP tool server architecture I built at JPMorgan Chase, just in the open.

## 04-gmail-inbox-labeler

Moves messages out of a Gmail inbox into existing labels by asking a **local** Ollama model to
classify each one — no email content ever leaves the machine to a hosted LLM. A deliberate privacy
constraint, not a limitation: it's a useful demonstration that "local-only" is a real design option
for LLM tooling, not just a fallback.

## 05-llm-cost-comparison

A stdlib-only Python tool that estimates and compares the real cost of running an LLM locally (owned
hardware or rented cloud GPU) against hosted APIs, using your own workload and, where it can, your own
measured hardware throughput. Deliberately dependency-free by choice, to keep it trivially portable —
not because the problem demanded it.

## 05-prize-draw-orchestrator

An MCP-driven agent that finds competition and prize-draw pages, filters them against configured
eligibility criteria, and reasons about entries using a swappable LLM backend (Ollama, DeepSeek, or
Claude), with dry-run and personal-data safety gates on by default. Currently integrates against a
documented stub interface rather than live sites.

## 06-octopus-agile-alert

A zero-dependency scheduled job that checks tomorrow's half-hourly Octopus Agile electricity prices and
sends a webhook alert when a slot drops below a configurable threshold, run on a daily GitHub Actions
cron. Small and unglamorous by design — it's the kind of automation I actually run for myself, not a
demo.
