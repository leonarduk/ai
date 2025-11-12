# 🧾 Log File Extraction Pipeline (Local LLM)

## Overview

This workflow uses a **local large language model (LLM)** to extract structured, relevant information from large log files. The extracted data is then passed to a **secondary LLM** for deeper analysis and potential resolution.

## Purpose

- ✅ Use a local LLM to **parse and annotate** raw log files.
- 🚫 Avoid interpretation, debugging, or code suggestions at this stage.
- 🎯 Prepare clean, structured output for a downstream LLM to analyze and fix.

## Workflow

1. **Paste the prompt** from `PROMPT.md` into the local LLM interface.
2. **Wait for confirmation** that the model understands the instructions.
3. **Attach the log file** for processing.
4. The local LLM will return a **structured Markdown summary** containing:
   - Errors
   - Stack traces
   - Warnings
   - Notable events
   - Metadata

## Files

- `PROMPT.md` – Contains the strict extraction-only prompt for the local LLM.
- `README.md` – This guide.

## Notes

- The prompt explicitly instructs the LLM **not to fix, explain, or interpret** errors.
- Output is designed for **handoff to another AI or developer**.
- Logs should be attached **after confirmation** to avoid premature analysis.
