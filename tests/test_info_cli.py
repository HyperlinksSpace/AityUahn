from click.testing import CliRunner

from python.cli import main


def test_info_command_unreachable():
    runner = CliRunner()
    result = runner.invoke(main, ["info", "--forge-url", "http://127.0.0.1:59999"])
    assert result.exit_code == 1
