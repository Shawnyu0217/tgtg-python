#!/usr/bin/env python3
import argparse
import json
import os
import sys


REQUIRED_ENV_VARS = [
    "TGTG_ACCESS_TOKEN",
    "TGTG_REFRESH_TOKEN",
    "TGTG_COOKIE",
]


def get_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value


def validate_env() -> dict:
    missing = []
    cfg: dict[str, str] = {}
    for var in REQUIRED_ENV_VARS:
        val = get_env(var)
        if not val:
            missing.append(var)
        else:
            cfg[var] = val
    if missing:
        sys.stderr.write(
            "Missing required environment variables: " + ", ".join(missing) + "\n"
        )
        sys.stderr.write(
            "Export your .env first, e.g.: export $(grep -v '^#' .env | xargs)\n"
        )
        sys.exit(1)
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="Check TGTG order status by id")
    parser.add_argument("order_id", nargs="?", help="Order id to check")
    parser.add_argument(
        "--raw", action="store_true", help="Print raw response instead of formatted JSON"
    )
    args = parser.parse_args()

    cfg = validate_env()

    order_id = args.order_id
    if not order_id:
        sys.stdout.write("Enter order id: ")
        sys.stdout.flush()
        order_id = sys.stdin.readline().strip()

    if not order_id:
        sys.stderr.write("No order id provided.\n")
        sys.exit(2)

    try:
        from tgtg import TgtgClient

        client = TgtgClient(
            access_token=cfg["TGTG_ACCESS_TOKEN"],
            refresh_token=cfg["TGTG_REFRESH_TOKEN"],
            cookie=cfg["TGTG_COOKIE"],
        )
    except Exception as e:
        sys.stderr.write("Failed to initialize TgtgClient: %s\n" % str(e))
        sys.exit(3)

    try:
        status = client.get_order_status(order_id)
    except Exception as e:
        sys.stderr.write("Failed to fetch order status: %s\n" % str(e))
        sys.exit(4)

    try:
        if args.raw:
            sys.stdout.write(str(status) + "\n")
        else:
            sys.stdout.write(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        sys.stdout.write(str(status) + "\n")


if __name__ == "__main__":
    main()


