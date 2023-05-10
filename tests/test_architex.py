from typer.testing import CliRunner

from architex import (
    DB_READ_ERROR,
    SUCCESS,
    __app_name__,
    __version__,
    view,
)

runner = CliRunner()


def test_version():
    result = runner.invoke(view.app, ["--version"])
    assert result.exit_code == 0
    assert f"{__app_name__} v{__version__}\n" in result.stdout
