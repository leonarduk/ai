# Prize Draw MCP Server

This MCP server exposes the mechanics needed to **find and enter prize
draws** as tools: search/discovery, entry-page fetching, entry submission,
and a local entry log. It contains **no LLM/provider-specific logic** -
deciding which draws to enter, what to say in free-text answers, and which
LLM backend to use for that reasoning is the job of an orchestrating client
(tracked separately as issue #23, parent issue #21). This server just does
scraping, parsing scaffolding, entry submission, and logging.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

No API keys are required to try the server - `search_draws` and
`parse_entry_page` work out of the box against the bundled mock/example
sources. Optional environment variables (via `.env` in the project root, or
the process environment):

```bash
# Only needed for entry_method=email in submit_entry
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Optional: override where the entry log JSONL file lives
# (defaults to ./data/draws.jsonl next to this server)
PRIZE_DRAW_STORE_PATH=/path/to/draws.jsonl
```

## Data store

Discovered/entered draws are tracked in an append-only JSONL file
(`data/draws.jsonl` by default, see `store.py`). Each line is one record:

| Field                | Type          | Notes                                                          |
|----------------------|---------------|-----------------------------------------------------------------|
| `draw_id`            | string        | Stable id, derived from `source:url` (see `sources.make_draw_id`) |
| `source`              | string        | Name of the configured source that produced the draw            |
| `title`               | string        | Human-readable title                                             |
| `prize`               | string        | Prize description                                                |
| `url`                 | string        | Entry page / feed item URL                                       |
| `closing_date`        | string \| null | ISO-8601 date the draw closes                                    |
| `entry_method`        | string \| null | `web_form` \| `email` \| `social`                                |
| `requires_purchase`   | bool          | Whether entry requires a purchase                                 |
| `status`              | string        | `discovered` \| `dry_run` \| `entered` \| `skipped` \| `failed`   |
| `entered_at`          | string \| null | ISO-8601 timestamp of a real (non-dry-run) entry                 |
| `notes`               | string        | Free-form notes / result details                                  |
| `updated_at`          | string        | ISO-8601 timestamp this line was written                          |

The file is append-only (a full audit trail); readers always resolve to the
**latest** line per `draw_id`. This keeps the store trivially simple (no
database dependency) while still fitting the repo's existing "plain files
next to the server" convention.

## Sources

`sources.py` holds a small, pluggable registry of source configs. Two
placeholder sources ship with the server, since real aggregator/RSS URLs
need to be scoped separately per issue #21:

- `mock-aggregator` (`type: "static"`) - a fixed example listing, no network
  access at all. Good for demos and offline tests.
- `example-rss` (`type: "rss"`) - fetches and parses a real RSS 2.0 feed.
  Point its `url` at a real feed to use it for real.

Add a new source by appending a dict to `SOURCES` with a `type` this module
understands (`static` or `rss`) - no other code changes are required.

## Tools

### `search_draws`

Poll configured source(s) for candidate prize draws and return raw listings.
Newly seen draws are also recorded in the log with `status: "discovered"`,
so `check_log` can be used for duplicate avoidance.

**Input:**

```json
{
  "sources": ["mock-aggregator"],
  "limit": 10
}
```

- `sources` (optional array of strings): names of configured sources to
  poll. Defaults to every configured source.
- `limit` (optional integer): cap the number of listings returned.

**Output:**

```json
{
  "count": 2,
  "listings": [
    {
      "draw_id": "mock-aggregator-...",
      "source": "mock-aggregator",
      "title": "Win a Weekend Spa Break for Two",
      "url": "https://example-competitions.test/spa-break",
      "prize": "Weekend spa break for two",
      "closing_date": "2026-08-15",
      "entry_method": "web_form",
      "requires_purchase": false,
      "summary": "Free entry, no purchase necessary."
    }
  ]
}
```

### `parse_entry_page`

Fetch a draw's entry page (or feed item URL) and return raw content for the
caller to interpret. No LLM call and no interpretation happens inside this
tool - just clean structured input for one. URLs starting with `mock://`
return a canned fixture with no network access at all, for demos/tests
(e.g. `mock://spa-break`).

**Input:**

```json
{
  "url": "https://example-competitions.test/spa-break",
  "include_html": false
}
```

- `url` (required string): entry page or feed item URL to fetch.
- `include_html` (optional bool, default `false`): include the raw HTML in
  the response as well as the cleaned text.

**Output:**

```json
{
  "url": "https://example-competitions.test/spa-break",
  "status_code": 200,
  "content_type": "text/html",
  "title": "Win a Weekend Spa Break",
  "content": "Enter now\nNo purchase necessary. Answer: what colour is the sky?",
  "content_length": 66
}
```

### `submit_entry`

Perform (or dry-run) the entry action for a draw, given already-resolved
field values from the caller (this tool does not decide what to put in the
fields - that is the orchestrating client's job).

Safety rules enforced unconditionally:

- **Duplicate avoidance**: refuses if the draw is already logged with
  `status: "entered"`.
- **Personal/financial data**: if any field name looks like personal or
  financial data (`email`, `name`, `address`, `phone`, `card`, `iban`, etc.
  - see `entry.PERSONAL_FIELD_MARKERS`), the submission is refused unless
  `confirm_personal_data: true` is explicitly passed.
- **Purchase requirement**: if the draw requires a purchase (either passed
  in via `requires_purchase` or already recorded in the log), the
  submission is refused unless `confirm_purchase_required: true` is
  explicitly passed.
- **Dry-run by default**: `dry_run` defaults to `true`. In dry-run mode, no
  network call/email/social action is performed; the tool logs what
  *would* be submitted (`status: "dry_run"`) and returns a preview.

**Input:**

```json
{
  "draw_id": "mock-aggregator-abc123",
  "entry_method": "web_form",
  "fields": {"answer": "blue"},
  "url": "https://example-competitions.test/spa-break",
  "dry_run": true
}
```

- `draw_id` (required string)
- `entry_method` (required string): `web_form` | `email` | `social`
- `fields` (object, default `{}`): resolved field values to submit
- `url` (string): entry form URL - required for `entry_method: "web_form"`
  (and used as the social profile/target URL for `entry_method: "social"`)
- `email_to`, `email_subject`, `email_body` (strings): used for
  `entry_method: "email"` (requires `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD`
  environment variables to actually send)
- `social_action` (string): required for `entry_method: "social"`, e.g.
  `"follow"`/`"like"`/`"retweet"` - see note below
- `requires_purchase` (bool, default `false`)
- `confirm_purchase_required` (bool, default `false`)
- `confirm_personal_data` (bool, default `false`)
- `dry_run` (bool, default `true`)
- `source` (string, default `"unknown"`): used for the log entry if the
  draw isn't already logged

**Output (dry run):**

```json
{
  "draw_id": "mock-aggregator-abc123",
  "status": "dry_run",
  "preview": {
    "draw_id": "mock-aggregator-abc123",
    "entry_method": "web_form",
    "fields": {"answer": "blue"},
    "would_submit": true
  }
}
```

**Output (real submission):**

```json
{
  "draw_id": "mock-aggregator-abc123",
  "status": "entered",
  "result": {"method": "web_form", "url": "...", "status_code": 200}
}
```

**Output (refused):**

```json
{
  "draw_id": "mock-aggregator-abc123",
  "status": "failed",
  "reason": "Fields look like personal/financial data (email); refusing unless confirm_personal_data=true is explicitly set."
}
```

> **Note on `entry_method: "social"`**: there is no generic,
> credential-free social API this server can call - each platform needs its
> own OAuth app, which is out of scope for this issue (see #21). Social
> submissions are recorded as `"simulated": true` in the result rather than
> silently pretending a live call happened; wiring up a real provider is
> future work.

### `check_log`

Query the entry log for previously seen/entered draws (duplicate
avoidance), or record a new entry/result directly (e.g. if a client tracks
an entry made outside of `submit_entry`).

**Input:**

```json
{"action": "list", "status": "entered"}
```

- `action` (required string): `list` | `get` | `has_seen` | `has_entered` |
  `record`
- `draw_id` (string): required for `get`/`has_seen`/`has_entered`/`record`
- `status` (string): filter for `action: "list"`, or the status to set for
  `action: "record"`
- `record` (object): full/partial draw record to upsert for
  `action: "record"`

**Output examples:**

```json
{"draws": [{"draw_id": "...", "status": "entered", "...": "..."}]}
```

```json
{"draw_id": "draw-1", "has_entered": true}
```

## Usage

Run the server:

```bash
python server.py
```

The server communicates via stdio using the MCP protocol.

## Tests

```bash
pip install -r requirements.txt pytest
pytest -v
```

All tests mock network calls (`requests.get`/`requests.post`) and SMTP
(`smtplib.SMTP`) - no test hits a real website or mail server, and each test
gets a fresh temp-file-backed store via an autouse fixture.
