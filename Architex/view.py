"""This module provides the architex CLI."""

import typer
from typing import Optional, List
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
    list_of_path: List[str] = typer.Argument(...),
    search: bool = typer.Option(False, "--search", "-s"),
) -> None:
    """Draw software architecture diagram."""
    controller.start_drawing(list_of_path, search)
    typer.secho(
        f"""Your architectural diagram is completed""",
        fg=typer.colors.GREEN,
    )
