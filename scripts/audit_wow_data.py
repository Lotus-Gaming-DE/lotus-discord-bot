"""Audit and optionally mark WoW Classic HC JSON data quality."""

from argparse import ArgumentParser
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lotus_bot.bot import load_wow_data
from lotus_bot.cogs.quiz.area_providers.wow_audit import (  # noqa: E402
    apply_wow_qa,
    audit_wow_data,
    write_wow_qa_data,
)


DEFAULT_DATA_PATH = ROOT / "data" / "wow" / "classic_hc"


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    data_path = Path(args.data_path)
    data = load_wow_data(data_path)

    if args.write:
        updated, report = apply_wow_qa(data)
        write_wow_qa_data(data_path, updated)
        print("WoW QA metadata written.")
    else:
        report = audit_wow_data(data)
        print("WoW QA preview. Use --write to persist metadata.")

    _print_report(report)


def _print_report(report: dict) -> None:
    summary = report.get("summary", {})
    examples = report.get("examples", {})
    if not summary:
        print("No QA findings.")
        return

    for table, flags in summary.items():
        print(f"\n{table}")
        for flag, count in flags.items():
            sample = ", ".join(examples.get(table, {}).get(flag, [])[:5])
            suffix = f" (examples: {sample})" if sample else ""
            print(f"  - {flag}: {count}{suffix}")


if __name__ == "__main__":  # pragma: no cover
    main()
