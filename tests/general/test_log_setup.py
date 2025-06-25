import json
import os

import lotus_bot.log_setup as log_setup


def test_setup_logging_writes_json(tmp_path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        log_setup._configured = False
        log_setup.setup_logging("INFO")
        logger = log_setup.get_logger("test")
        logger.info("hello", value=1)
    finally:
        os.chdir(old_cwd)

    log_file = tmp_path / "logs" / "bot.json"
    assert log_file.exists()
    data = json.loads(log_file.read_text().splitlines()[-1])
    assert data["event"] == "hello"
    assert data["value"] == 1
