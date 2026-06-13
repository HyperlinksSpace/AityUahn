from click.testing import CliRunner

from python.cli import main


def test_doctor_json_when_forge_unreachable():
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--forge-url", "http://127.0.0.1:59999", "--json-out"])
    assert result.exit_code == 1
    assert '"ok": false' in result.output.lower() or '"ok":false' in result.output.replace(" ", "")
