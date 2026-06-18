from click.testing import CliRunner

from python.cli import main


def test_urls_command():
    runner = CliRunner()
    result = runner.invoke(main, ["urls"])
    assert result.exit_code == 0
    assert "controller.html" in result.output
    assert "8765" in result.output


def test_urls_json():
    runner = CliRunner()
    result = runner.invoke(main, ["urls", "--json-out"])
    assert result.exit_code == 0
    assert '"health"' in result.output
