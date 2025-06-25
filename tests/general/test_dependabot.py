import yaml
from pathlib import Path


def test_dependabot_config_exists():
    path = Path(".github/dependabot.yml")
    assert path.is_file(), "dependabot.yml not found"

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data.get("version") == 2
    updates = data.get("updates", [])
    assert any(u.get("package-ecosystem") == "github-actions" for u in updates)
    assert any(u.get("package-ecosystem") == "pip" for u in updates)
