from click.testing import CliRunner

from python.cli import main


def test_ping_fails_when_offline():
    runner = CliRunner()
    result = runner.invoke(main, ["ping", "--forge-url", "http://127.0.0.1:59999", "-q"])
    assert result.exit_code == 1
    assert "fail" in result.output.lower()
