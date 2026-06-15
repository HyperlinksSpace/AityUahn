from click.testing import CliRunner

from python.cli import main
from python.verify_setup import run_verification


def test_verify_command_fails_when_forge_down():
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--forge-url", "http://127.0.0.1:59999"])
    assert result.exit_code == 1
    assert "Verification failed" in result.output or "fail" in result.output.lower()


def test_run_verification_forge_unreachable():
    report = run_verification("http://127.0.0.1:59999")
    assert report.ok is False
    assert report.checks[0].name == "forge"
    assert report.checks[0].ok is False
