"""This module provides the architex CLI."""

import typer
from typing import Optional
from architex import (ERRORS, __app_name__, __version__, controller)

app = typer.Typer()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return


@app.command()
def draw(
    repo_path: str = typer.Argument(...),
) -> None:
    """Draw software architecture diagram."""
    controller.start_drawing(repo_path)
    typer.secho(
        f"""Your architectural diagram is completed""",
        fg=typer.colors.GREEN,
    )
