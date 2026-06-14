from click.testing import CliRunner

from python.cli import main


def test_version_command():
    runner = CliRunner()
    result = runner.invoke(main, ["version"])
    assert result.exit_code == 0
    assert "aityuahn" in result.output
    assert "0.2." in result.output
