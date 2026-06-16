from click.testing import CliRunner

from python.cli import main


def test_dashboard_command_unreachable():
    runner = CliRunner()
    result = runner.invoke(main, ["dashboard", "--forge-url", "http://127.0.0.1:59999"])
    assert result.exit_code == 1
    assert "serve" in result.output.lower() or "Could not fetch" in result.output
