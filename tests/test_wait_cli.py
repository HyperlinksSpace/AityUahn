from click.testing import CliRunner

from python.cli import main
from python.wait_for import wait_for_services


def test_wait_command_times_out():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["wait", "--forge-url", "http://127.0.0.1:59999", "--timeout", "0.5", "--interval", "0.1"],
    )
    assert result.exit_code == 1
    assert "Timed out" in result.output


def test_wait_for_services_false():
    assert wait_for_services("http://127.0.0.1:59999", timeout=0.3, interval=0.1) is False
