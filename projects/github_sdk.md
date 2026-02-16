# AI Agent Prototype Plan – GitHub Copilot SDK + AWS

## 1. Objective

**Goal:** Build a small but credible AI agent that:
- Analyses a GitHub repo
- Infers current architecture and AWS usage
- Proposes a modernization plan (clear, structured, actionable)

Target outcome: a demo‑ready prototype you can show as part of your “future‑ready engineering” story.

---

## 2. High-level concept

**Agent prompt:**
- Input: repo URL or local path, optional “focus” (e.g. cost, resilience, latency).
- Output: markdown report with:
  - Current architecture summary
  - Detected AWS services and patterns
  - Risks / smells (e.g. tight coupling, single-region, no IaC)
  - Modernization recommendations (prioritized, with rationale)

**Core capabilities:**
- Read/scan codebase
- Extract architecture signals (frameworks, configs, IaC, CI/CD)
- Use tools to:
  - List files
  - Read file contents
  - Optionally call AWS APIs (if credentials available)
- Produce structured, opinionated guidance

---

## 3. Tech stack & components

**Language:** Python (first), with option to mirror in TypeScript later.  
**Runtime:** GitHub Copilot SDK (technical preview).  
**Execution surfaces:**
- CLI command (primary)
- Optional: GitHub Action wrapper later

**Components:**
- **Agent definition:** system prompt, tools, memory config
- **Tools:**
  - Repo file lister
  - File reader / code snippet fetcher
  - Optional: AWS introspection (e.g. `boto3` calls)
- **Planner:** multi-step reasoning (scan → infer → recommend)
- **Report generator:** markdown formatter

---

## 4. Milestones

### Milestone 1 – Skeleton agent

- **Define agent:**
  - System prompt: role, tone, constraints
  - Basic tools: list files, read file
- **Happy-path flow:**
  - Input: local path
  - Agent scans key files (e.g. `pom.xml`, `build.gradle`, `requirements.txt`, `Dockerfile`, `serverless.yml`, `cdk.json`, `terraform` dirs)
  - Output: simple text summary of stack

**Success