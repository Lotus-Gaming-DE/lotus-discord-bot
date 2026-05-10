"""Import curated WoW Classic HC data.

Usage:
    python scripts/import_wow_data.py --slice instances --ids 2100,1977 --preview
    python scripts/import_wow_data.py --slice instances --ids 2100 --limit-drops 10 --write
"""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lotus_bot.cogs.quiz.area_providers.wow_importer import main


if __name__ == "__main__":  # pragma: no cover
    main()
