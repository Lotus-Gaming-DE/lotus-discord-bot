"""Fetch Warcraft Rumble data and show unit count.

Usage: python scripts/fetch_wcr.py [--url URL]
"""
import argparse
import asyncio
import os
from lotus_bot.cogs.wcr.utils import fetch_wcr_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch WCR data and show stats")
    parser.add_argument("--url", default=os.getenv("WCR_API_URL"), help="API base URL")
    return parser.parse_args()


async def run(url: str) -> None:
    data = await fetch_wcr_data(base_url=url)
    units = data.get("units")
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    print(f"Fetched {len(units)} units.")


def main() -> None:
    args = parse_args()
    if not args.url:
        raise SystemExit("WCR_API_URL not provided")
    asyncio.run(run(args.url))


if __name__ == "__main__":  # pragma: no cover
    main()
