from click.testing import CliRunner

from python.cli import main
from python.status_report import build_status_report

from tests.test_api import _test_forge


def test_status_command_json():
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--json-out"])
    assert result.exit_code == 0
    assert '"version"' in result.output
    assert '"workspace"' in result.output or "workspace" in result.output


def test_status_report_offline_forge(tmp_path):
    forge = _test_forge(tmp_path)
    report = build_status_report(forge, "http://127.0.0.1:59999")
    assert report.forge_reachable is False
    assert report.version.startswith("0.2.")
