from pathlib import Path

from click.testing import CliRunner

from python.cli import main
from python.demo import seed_demo_data

from tests.test_api import _test_forge


def test_tasks_local_demo_slug(tmp_path: Path):
    forge = _test_forge(tmp_path)
    seed_demo_data(forge.storage)
    runner = CliRunner()
    result = runner.invoke(main, ["tasks", "demo-dashboard"])
    assert result.exit_code == 0
    assert "T-demo" in result.output
    assert "done" in result.output.lower() or "in_progress" in result.output


def test_tasks_json_out(tmp_path: Path):
    forge = _test_forge(tmp_path)
    seed_demo_data(forge.storage)
    runner = CliRunner()
    result = runner.invoke(main, ["tasks", "demo-dashboard", "--json-out"])
    assert result.exit_code == 0
    assert '"tasks"' in result.output
