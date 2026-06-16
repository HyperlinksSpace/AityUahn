from click.testing import CliRunner

from python.cli import main


def test_config_command():
    runner = CliRunner()
    result = runner.invoke(main, ["config", "--json-out"])
    assert result.exit_code == 0
    assert "workspace_root" in result.output
    assert "providers" in result.output
