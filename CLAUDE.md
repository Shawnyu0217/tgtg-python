# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an unofficial Python client for the TooGoodToGo API. It provides a wrapper around TGTG's REST endpoints for managing user authentication, fetching items/stores, managing favorites, and creating/managing orders.

**Key Domain Concepts:**
- **Authentication Flow**: Email-based polling authentication (user receives email, clicks link, client polls for success)
- **Token Management**: Access tokens expire after ~4 hours and are automatically refreshed using refresh tokens
- **Cookie Management**: The API requires a specific cookie (datadome) from the Set-Cookie header, which must be maintained across requests
- **Items vs Favorites**: `get_items()` requires location data unless `favorites_only=True`; `get_favorites()` uses a different endpoint (`/bucket`) and mimics the official app behavior more closely

## Development Commands

**Setup:**
```bash
# Install dependencies (requires Poetry)
poetry install

# Install pre-commit hooks
pre-commit install
```

**Testing:**
```bash
# Run all tests with coverage
make test
# Or directly:
poetry run pytest

# Run specific test file
poetry run pytest tests/test_login.py

# Run specific test
poetry run pytest tests/test_login.py::test_login_with_tokens
```

**Linting:**
```bash
# Run all pre-commit hooks (black, isort, flake8)
make lint
# Or directly:
poetry run pre-commit run -a
```

**Publishing:**
```bash
make publish
```

## Architecture

### Core Client Structure

**Main Client** (`tgtg/__init__.py`):
- `TgtgClient` class handles all API interactions
- Uses `requests.Session` for connection pooling and header management
- All methods that interact with the API call `self.login()` first to ensure valid tokens

**Authentication State Machine**:
1. If `access_token`, `refresh_token`, `cookie` provided → refresh token if expired
2. If only `email` provided → initiate email auth flow → poll for user confirmation
3. Token refresh happens automatically if `last_time_token_refreshed` is older than `access_token_lifetime` (default 4 hours)

**Headers Management** (`_headers` property):
- Dynamically builds headers based on authentication state
- Always includes `user-agent` (mimics Android TGTG app)
- Includes `authorization` header when `access_token` is set
- Includes `Cookie` header when `cookie` is set
- Uses `x-correlation-id` for unauthenticated requests

**User Agent Strategy**:
- Attempts to scrape latest APK version from Google Play using `google_play_scraper.py`
- Falls back to `DEFAULT_APK_VERSION` if scraping fails
- Randomly selects from multiple Android device profiles to mimic real app traffic

### Exception Hierarchy

- `TgtgLoginError`: Raised when authentication fails (wrong credentials, polling timeout)
- `TgtgAPIError`: Raised for general API errors (HTTP errors, rate limiting, invalid responses)
- `TgtgPollingError`: Raised specifically when polling times out or email link not clicked

### Scripts

**`scripts/authentication.py`**:
- Standalone script to retrieve fresh credentials
- Prompts for email, handles polling flow
- Outputs credentials JSON for use in other applications

**`scripts/watch_favorites.py`**:
- Production-ready monitoring daemon for favorite stores
- Tracks availability state changes (0 → >0 items triggers notification)
- Requires environment variables: `TGTG_ACCESS_TOKEN`, `TGTG_REFRESH_TOKEN`, `TGTG_COOKIE`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TGTG_POLL_MINUTES_MIN`, `TGTG_POLL_MINUTES_MAX`
- Maintains state in JSON file (default: `.tgtg-watcher/state.json`)
- Supports `--loop` flag for continuous monitoring with jittered polling

### Testing Architecture

**Test Structure**:
- Uses `pytest` with `responses` library to mock HTTP interactions
- `tests/conftest.py` provides shared fixtures for authentication mocks
- `tgtg_client_fake_tokens` constant in `tests/constants.py` provides test credentials

**Running Tests in Isolation**:
- Tests use `@responses.activate` decorator to mock HTTP calls
- Each test function-scoped fixture ensures clean state
- Use `pytest -k <pattern>` to run subset of tests

## Common Patterns

**Creating a client with existing credentials:**
```python
from tgtg import TgtgClient
client = TgtgClient(
    access_token="your_token",
    refresh_token="your_refresh",
    cookie="datadome_cookie_value"
)
```

**First-time authentication flow:**
```python
from tgtg import TgtgClient
client = TgtgClient(email="user@example.com")
credentials = client.get_credentials()  # Blocks until email link clicked
```

**Working with favorites vs items:**
- Use `get_favorites()` for user's saved stores (matches app behavior)
- Use `get_items(favorites_only=True)` for similar results via different endpoint
- Use `get_items(favorites_only=False, latitude=X, longitude=Y, radius=R)` for location-based search

## Important Implementation Notes

- **Rate Limiting**: API returns 429 Too Many Requests when rate limited. The client raises `TgtgAPIError` with this status code.
- **Polling Behavior**: Authentication polling tries 24 times with 5-second intervals (2 minutes total). Email must be opened on desktop browser if TGTG app is installed on mobile.
- **Token Refresh**: Happens automatically on any API call if tokens are older than `access_token_lifetime`. New cookie is extracted from `Set-Cookie` header.
- **CAPTCHA Bypass**: The `login()` method intentionally sends the auth request twice to attempt CAPTCHA bypass (line 150 in `tgtg/__init__.py`).
- **Order Payment**: The `create_order()` method creates an order but does NOT handle payment. Orders created via this API must be paid through other means.
- **Pagination**: `get_inactive()` supports pagination via `page` and `page_size` parameters. Response includes `has_more` boolean to indicate additional pages.

## Code Style

- **Formatting**: Black (enforced via pre-commit)
- **Import Sorting**: isort with black profile (enforced via pre-commit)
- **Linting**: flake8 with max-line-length=119, max-complexity=10
- **Coverage**: Tests should maintain coverage (pytest-cov configured)

## Git Workflow

- Main branch: `master`
- Pre-commit hooks run black, isort, and flake8 automatically
- CI runs via GitHub Actions (see `.github/workflows/`)
