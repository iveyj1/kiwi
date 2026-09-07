#!/usr/bin/env python3
"""Export the KiwiSDR public receiver directory as structured JSON."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from kiwi_client.public_directory import PUBLIC_DIRECTORY_URL, fetch_public_directory, parse_public_directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=PUBLIC_DIRECTORY_URL)
    parser.add_argument("--html", type=Path, help="parse saved directory HTML instead of fetching")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    document = args.html.read_text(encoding="utf-8") if args.html else fetch_public_directory(url=args.url, timeout=args.timeout)
    receivers = parse_public_directory(document)
    payload = {
        "source": args.url,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "receiver_count": len(receivers),
        "receivers": receivers,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(receivers)} receivers to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
