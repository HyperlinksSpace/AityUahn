from click.testing import CliRunner

from python.cli import main


def test_open_command_prints_url():
    runner = CliRunner()
    result = runner.invoke(main, ["open", "--page", "guide"])
    assert result.exit_code == 0
    assert "guide.html" in result.output
