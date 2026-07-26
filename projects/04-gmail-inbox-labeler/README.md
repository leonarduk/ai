# Gmail Inbox Labeler

Moves messages out of a Gmail inbox into one or more existing labels, using a
**local Ollama model** to decide which label(s) each message belongs to. No
email content is ever sent to a hosted/cloud LLM.

## How it works

1. Authenticates to the Gmail API (OAuth2, `gmail.modify` scope).
2. Lists the user's existing labels (these become the classifier's choices —
   create the labels you want in Gmail first).
3. For each message currently in the inbox, sends the subject/sender/snippet
   to a local Ollama model and asks it to pick zero, one, or several of the
   existing labels.
4. Applies the chosen label(s) and removes `INBOX`, so the message moves out
   of the inbox. Messages the model doesn't confidently match to any label
   are left alone.

Re-running the script is safe: it only ever queries `in:inbox` (or a custom
`--query`), so messages already moved out of the inbox aren't touched again.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a Gmail OAuth client: Google Cloud Console → APIs & Services →
   Credentials → Create Credentials → OAuth client ID → Desktop app. Download
   the JSON and save it as `credentials.json` in this folder (or point
   `GMAIL_CREDENTIALS_PATH` elsewhere).
3. Make sure [Ollama](https://ollama.com) is running locally with a model
   pulled, e.g.:
   ```bash
   ollama pull qwen2.5-coder:14b
   ollama serve
   ```
   Small models (~3B, e.g. `llama3.2`) tend to pick several loosely-related
   labels per email when given a large/nested label set - a ~7B+ model gives
   much more precise, usually single-label results. Always check a
   `--dry-run` against your real inbox and label set before a live run.
4. Copy `.env.example` to `.env` and adjust as needed.

The first run opens a browser window for the Gmail OAuth consent screen and
caches the resulting token at `GMAIL_TOKEN_PATH` (default `token.json`) so
subsequent runs are non-interactive.

`credentials.json` and `token.json` contain secrets — never commit them
(already covered by `.gitignore`).

## Usage

Preview what the script would do without changing anything:
```bash
python label_inbox.py --dry-run
```

Actually move messages:
```bash
python label_inbox.py
```

Useful flags:
| Flag | Default | Description |
|---|---|---|
| `--query` | `in:inbox` | Gmail search query selecting which messages to process |
| `--max-results` | `100` | Max messages to process in one run |
| `--model` | `llama3` (or `OLLAMA_MODEL`) | Local Ollama model to use |
| `--ollama-host` | `http://localhost:11434` (or `OLLAMA_HOST`) | Local Ollama server URL |
| `--dry-run` | off | Log decisions without modifying any message |
| `--verbose` | off | Enable debug logging |

## Tests

```bash
python -m pytest tests/ -v
```
