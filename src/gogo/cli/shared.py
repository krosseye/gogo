from collections.abc import Iterable, Sequence
from typing import NoReturn

import typer
from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def print_success(message: str) -> None:
    console.print(f"[green]Success:[/green] {message}")


def print_warning(message: str) -> None:
    err_console.print(f"[yellow]Warning:[/yellow] {message}")


def print_error(message: str) -> NoReturn:
    err_console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def build_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    show_lines: bool = True,
) -> Table:
    table = Table(show_lines=show_lines)
    for h in headers:
        table.add_column(h, style="bold")

    for row in rows:
        table.add_row(*row)

    return table


def print_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    show_lines: bool = True,
) -> None:
    table = build_table(headers, rows, show_lines=show_lines)
    console.print(table)
