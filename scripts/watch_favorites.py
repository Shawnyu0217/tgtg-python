import sys
from pathlib import Path

# Ensure project root is in sys.path for direct execution
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import requests


REQUIRED_ENV_VARS = [
    "TGTG_ACCESS_TOKEN",
    "TGTG_REFRESH_TOKEN",
    "TGTG_COOKIE",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TGTG_POLL_MINUTES_MIN",
    "TGTG_POLL_MINUTES_MAX"
]


def get_env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value


def print_missing_vars(missing: list[str]) -> None:
    sys.stderr.write(
        "Missing required environment variables: " + ", ".join(missing) + "\n"
    )
    sys.stderr.write(
        "Hint: create a .env file at the project root (see examples/.env.example) and export it before running.\n"
    )
    sys.stderr.write(
        "Example (zsh/bash): export $(grep -v '^#' .env | xargs) && python scripts/watch_favorites.py\n"
    )


def validate_env() -> dict:
    missing = []
    config: dict[str, str] = {}
    for var in REQUIRED_ENV_VARS:
        val = get_env(var)
        if not val:
            missing.append(var)
        else:
            config[var] = val

    # Optional settings with defaults
    poll_min = int(os.environ.get("TGTG_POLL_MINUTES_MIN", "10"))
    poll_max = int(os.environ.get("TGTG_POLL_MINUTES_MAX", "15"))
    repo_root = Path(__file__).resolve().parent.parent
    default_state_path = str(repo_root / ".tgtg-watcher" / "state.json")
    state_path = os.path.expanduser(os.environ.get("TGTG_STATE_PATH", default_state_path))

    if poll_min <= 0 or poll_max <= 0 or poll_min > poll_max:
        sys.stderr.write(
            "Invalid polling window: ensure 0 < MIN <= MAX (got MIN=%d, MAX=%d)\n"
            % (poll_min, poll_max)
        )
        sys.exit(2)

    if missing:
        print_missing_vars(missing)
        sys.exit(1)

    config.update(
        {
            "TGTG_POLL_MINUTES_MIN": str(poll_min),
            "TGTG_POLL_MINUTES_MAX": str(poll_max),
            "TGTG_STATE_PATH": state_path,
        }
    )
    return config


def ensure_state_dir(state_path: str) -> None:
    path = Path(state_path).expanduser()
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def load_state(state_path: str) -> Dict[str, Dict[str, Any]]:
    ensure_state_dir(state_path)
    p = Path(state_path).expanduser()
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupt or unreadable: start fresh (MVP minimal handling)
        return {}


def save_state(state_path: str, state: Dict[str, Dict[str, Any]]) -> None:
    ensure_state_dir(state_path)
    p = Path(state_path).expanduser()
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(p)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_top_level_int(d: Dict[str, Any], key: str, default: int = 0) -> int:
    try:
        v = d.get(key, default)
        return int(v)
    except Exception:
        return default


def extract_item_id(entry: Dict[str, Any]) -> Optional[str]:
    try:
        item = entry.get("item") or {}
        item_id = item.get("item_id")
        if item_id is None:
            return None
        return str(item_id)
    except Exception:
        return None


def describe_entry(entry: Dict[str, Any]) -> str:
    # Build a concise human-readable description
    item = entry.get("item", {})
    store = entry.get("store", {})
    display_name = entry.get("display_name") or item.get("name") or store.get("store_name") or "<unknown>"
    items_available = get_top_level_int(entry, "items_available", 0)
    # price (best-effort from item)
    price = item.get("price_including_taxes") or item.get("item_price") or {}
    code = price.get("code")
    mu = price.get("minor_units")
    dec = price.get("decimals", 2)
    price_str = "?"
    try:
        if code is not None and mu is not None:
            price_str = f"{mu / (10 ** int(dec)):.2f}{code}"
    except Exception:
        pass
    # pickup window (if present)
    pickup = entry.get("pickup_interval") or {}
    start = pickup.get("start")
    end = pickup.get("end")
    pickup_str = f" [{start} → {end}]" if start and end else ""
    return f"{display_name} | available={items_available} | price={price_str}{pickup_str}"


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        sys.stderr.write("Telegram notification failed: %s\n" % (str(e)))

def detect_new_availability(
    favorites: list[Dict[str, Any]], state: Dict[str, Dict[str, Any]]
) -> list[Dict[str, Any]]:
    newly_available: list[Dict[str, Any]] = []
    for entry in favorites:
        item_id = extract_item_id(entry)
        if not item_id:
            continue
        available_now = get_top_level_int(entry, "items_available", 0) > 0
        prev = state.get(item_id, {})
        was_available = bool(prev.get("was_available", False))
        if available_now and not was_available:
            newly_available.append(entry)
    return newly_available


def update_state_from_favorites(
    favorites: list[Dict[str, Any]], state: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    now = iso_now()
    for entry in favorites:
        item_id = extract_item_id(entry)
        if not item_id:
            continue
        available_now = get_top_level_int(entry, "items_available", 0) > 0
        state[item_id] = {
            "was_available": available_now,
            "last_seen_ts": now,
        }
    return state


def run_once(cfg: dict, client) -> int:
    # Dry fetch to validate credentials/connectivity
    try:
        favorites = client.get_favorites()
        try:
            count = len(favorites)  # typically a list
            sys.stdout.write("Fetched favorites successfully: %d items\n" % count)
        except Exception:
            sys.stdout.write("Fetched favorites successfully.\n")
    except Exception as e:
        msg = str(e)
        # Common cause: Geo/Captcha/403 due to cookie/token issues
        if "403" in msg or "captcha" in msg.lower():
            sys.stderr.write(
                "Failed to fetch favorites (possible 403/captcha). Try refreshing tokens/cookie.\n"
            )
            sys.stderr.write(
                "- Ensure TGTG_COOKIE is current (datadome value may change).\n"
            )
            sys.stderr.write(
                "- If tokens expired, re-authenticate and update TGTG_ACCESS_TOKEN/TGTG_REFRESH_TOKEN.\n"
            )
        else:
            sys.stderr.write("Failed to fetch favorites: %s\n" % msg)
        return 3

    # Load state, detect newly available, and interact
    state_path = cfg["TGTG_STATE_PATH"]
    state = load_state(state_path)
    newly = detect_new_availability(favorites, state)

    if not newly:
        sys.stdout.write("No newly available favorites detected.\n")
    else:
        sys.stdout.write("Newly available favorites (%d):\n" % len(newly))
        for idx, entry in enumerate(newly, start=1):
            item_id = extract_item_id(entry) or "<unknown>"
            summary = describe_entry(entry)
            sys.stdout.write("  %d) %s (item_id=%s)\n" % (idx, summary, item_id))
            try:
                text = f"TGTG: {summary} (item_id={item_id})"
                send_telegram_message(cfg["TELEGRAM_BOT_TOKEN"], cfg["TELEGRAM_CHAT_ID"], text)
                sys.stdout.write("   → Telegram notification sent.\n")
            except Exception as ne:
                sys.stderr.write("   → Telegram notification error: %s\n" % (str(ne)))

    # Persist updated availability state after processing
    state = update_state_from_favorites(favorites, state)
    save_state(state_path, state)
    sys.stdout.write("State saved to %s\n" % state_path)
    return 0


def random_sleep_seconds(min_minutes: int, max_minutes: int) -> float:
    try:
        import random

        return float(random.randint(min_minutes, max_minutes)) * 60.0
    except Exception:
        return float(min_minutes) * 60.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch TGTG favorites for availability")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously with jittered sleep between polls",
    )
    args = parser.parse_args()
    # Validate configuration
    cfg = validate_env()
    sys.stdout.write(
        "Configuration OK. Poll window: %s-%s minutes. State path: %s\n"
        % (
            cfg["TGTG_POLL_MINUTES_MIN"],
            cfg["TGTG_POLL_MINUTES_MAX"],
            cfg["TGTG_STATE_PATH"],
        )
    )

    # Initialize TGTG client
    try:
        from tgtg import TgtgClient

        client = TgtgClient(
            access_token=cfg["TGTG_ACCESS_TOKEN"],
            refresh_token=cfg["TGTG_REFRESH_TOKEN"],
            cookie=cfg["TGTG_COOKIE"],
        )
    except Exception as e:
        sys.stderr.write("Failed to initialize TgtgClient: %s\n" % (str(e)))
        sys.exit(2)

    if not args.loop:
        code = run_once(cfg, client)
        sys.exit(code)

    # Loop mode with jitter and simple backoff
    min_minutes = int(cfg["TGTG_POLL_MINUTES_MIN"])
    max_minutes = int(cfg["TGTG_POLL_MINUTES_MAX"])
    backoff_minutes = 0
    while True:
        code = run_once(cfg, client)
        try:
            import time

            if code == 0:
                backoff_minutes = 0
                sleep_seconds = random_sleep_seconds(min_minutes, max_minutes)
            else:
                backoff_minutes = min(backoff_minutes + 1, max_minutes)
                sleep_seconds = float(backoff_minutes) * 60.0
            time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            sys.stdout.write("Interrupted. Exiting.\n")
            break

if __name__ == "__main__":
    main()
