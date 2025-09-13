🛠️ Action Plan (MVP): TooGoodToGo Favorites Watcher — Telegram Only

### Objectives and Scope
- Goal: CLI that watches TGTG favorites and sends Telegram notifications on new availability. No ordering.
- Scope (MVP): favorites-only, single account, non-interactive CLI, polling every 10–15 minutes with jitter (adjustable).
- Out of scope (for now): interactive prompts, auto-order rules, multi-account, Docker/cron packaging, changes to `tgtg/` library.

### Prerequisites and Repository Context
- Python 3.9+.
- This repo already depends on `tgtg` (unofficial client) and `requests` (via Poetry).
- `.env` is gitignored in `.gitignore`.
- Relevant library capabilities (from `README.md`):
  - Get favorites: `client.get_favorites()` → `/api/discover/vX/bucket`.

### Architecture Overview
- Components:
  - Config loader: reads tokens and settings from environment (via `.env` loaded by the shell) and validates presence.
  - TGTG client: `from tgtg import TgtgClient` built using provided tokens.
  - Poller: fetches favorites periodically, computes diffs vs state to detect newly available items.
  - State manager: persists availability state per `item_id` to a local JSON file.
  - Notifier: sends a Telegram message for each newly available item.
- Data flow:
  - Env → Config → `TgtgClient` → Poll favorites → Detect new availability → Send Telegram message(s) → Update state → Sleep with jitter → repeat.
- Error handling:
  - Transient errors backoff; concise user-facing messages; no stack traces by default.
- Security:
  - Secrets only in env; never persisted to state; `.env` is already gitignored.
- Portability:
  - Pure Python with existing dependency (`tgtg`); works on macOS and Raspberry Pi (Python 3.9+).

### Codebase Structure (MVP additions only)
- Files:
  - `scripts/watch_favorites.py` — single CLI entrypoint containing config load, polling loop, state, and Telegram notifications.
  - `examples/.env.example` — documented environment variables and defaults.
- No changes to existing `tgtg/` package code in MVP.
- State file location (default): `~/.config/tgtg-watcher/state.json` (portable and outside the repo).

### Configuration (.env keys)
- Required:
  - `TGTG_ACCESS_TOKEN`
  - `TGTG_REFRESH_TOKEN`
  - `TGTG_COOKIE`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
- Optional (with defaults):
  - `TGTG_POLL_MINUTES_MIN=10`
  - `TGTG_POLL_MINUTES_MAX=15`
  - `TGTG_STATE_PATH=~/.config/tgtg-watcher/state.json`
- Notes:
  - Ensure your shell loads `.env` or export variables before running.
  - Do not store tokens in the repo. `.env` is already ignored.
  - Example `.env` (place at project root, never commit):
    
    TGTG_ACCESS_TOKEN="<access_token>"
    TGTG_REFRESH_TOKEN="<refresh_token>"
    TGTG_COOKIE="<cookie>"
    TELEGRAM_BOT_TOKEN="<bot_token>"
    TELEGRAM_CHAT_ID="<chat_id>"
    # Optional polling window (minutes)
    TGTG_POLL_MINUTES_MIN=10
    TGTG_POLL_MINUTES_MAX=15
    # Optional explicit state path
    # TGTG_STATE_PATH=~/.config/tgtg-watcher/state.json

### State Schema
- File: `~/.config/tgtg-watcher/state.json`
- Shape (example):
  - `{ "614318": { "was_available": true, "last_seen_ts": "2025-09-13T12:34:56Z" } }`
- Trigger definition:
  - Newly available = transition from absent/`was_available=false` to `items_available > 0`.

### Notification Content
- For each newly available item, send a Telegram message containing:
  - Display name (store/item)
  - `items_available`
  - Price (if present)
  - Pickup window (if present)
  - `item_id`

### CLI Flow
1. Startup: read env, validate required tokens, load state (create if missing).
2. Poll favorites via `client.get_favorites()`.
3. Filter items with `items_available > 0`.
4. Diff against state to find newly available items.
5. Send a Telegram message for each new item.
6. Persist state and sleep random minutes in `[POLL_MIN, POLL_MAX]`.

### Polling and Backoff
- Main cadence: random sleep between `TGTG_POLL_MINUTES_MIN` and `TGTG_POLL_MINUTES_MAX`.
- On transient failures (network/5xx): exponential backoff up to `POLL_MAX`.
- On 401/403: print guidance to refresh tokens and continue after normal sleep.

### Acceptance Criteria
- Running `python scripts/watch_favorites.py --loop` with valid env:
  - Polls every ~10–15 minutes (adjustable via env).
  - Detects and sends Telegram notifications for newly available favorites once per availability event.
  - Persists state so the same availability is not re-notified immediately.
  - Handles transient errors gracefully without crashing.

### Risks and Mitigations
- Token expiry or invalidation → clear message to refresh tokens; continue polling.
- API changes → keep logic minimal and close to library interfaces to reduce breakage.
- Telegram delivery issues (invalid token/chat id) → surface concise error and continue.

### Backlog (Post-MVP Enhancements)
- Additional notification channels (Slack/Email).
- Auto-order rules (store allowlist, price cap, time window).
- Packaging as console script (Poetry) and/or Docker; cron/launchd templates.
- Secret storage via OS keychain.
- Multi-account support.

### Runbook (Quick Start)
1. Ensure Python 3.9+ is available.
2. Install project deps if needed:
   - `pip install tgtg`
3. Create a `.env` at repo root (use the example above) with your `TGTG_*` tokens and Telegram variables.
4. Run: `python scripts/watch_favorites.py --loop`.
5. Keep terminal open to see logs.
6. If tokens expire, update `.env` and restart the script.

### Execution Checklist
1. Update `scripts/watch_favorites.py` to remove ordering and prompts; add Telegram notifications.
2. Add/update `examples/.env.example` with required/optional variables and comments.
3. Manually verify on macOS with real tokens; validate acceptance criteria.
4. Prepare notes for Raspberry Pi deployment (Python version, service runner) for next iteration.