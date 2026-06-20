from click.testing import CliRunner

from python.checkup import run_checkup
from python.cli import main
from tests.test_api import _test_forge


def test_checkup_local_only(tmp_path):
    forge = _test_forge(tmp_path)
    report = run_checkup(forge, "http://127.0.0.1:59999")
    assert report.version.startswith("0.2.")
    assert report.ok is False
    assert any("serve" in h for h in report.hints)


def test_checkup_cli_json():
    runner = CliRunner()
    result = runner.invoke(main, ["checkup", "--json-out"])
    assert result.exit_code == 1
    assert '"version"' in result.output
    assert '"checks"' in result.output
