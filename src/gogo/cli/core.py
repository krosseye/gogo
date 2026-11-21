import json

import typer

from gogo.core import name_gen
from gogo.core.config import config as app_config
from gogo.core.constants import APP_VERSION

from .engine import engine_app
from .shared import print_table

app = typer.Typer(
    name="gogo",
    help="A tool to manage Godot Engine versions and projects.",
    rich_markup_mode="rich",
)

project_app = typer.Typer(
    name="project",
    help="[bold blue]Manage Godot projects.[/bold blue]",
    short_help="Manage projects.",
)

app.add_typer(engine_app, name="engine")
app.add_typer(project_app, name="project")


@app.command()
def version() -> None:
    """Show the gogo CLI version."""
    typer.echo(f"gogo version {APP_VERSION}")


@app.command()
def config(
    output_json: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """Show configuration."""
    cfg = app_config.copy()

    if output_json:
        typer.echo(json.dumps(cfg, indent=2))
        return

    rows = [(k.replace("_", " ").title(), str(v)) for k, v in cfg.items()]
    print_table(["Key", "Value"], rows)


@app.command()
def generate_name(
    count: int = typer.Option(1, "--count", "-c", help="Number of names to generate."),
    output_json: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """Generate random names."""
    names = [name_gen.generate_name() for _ in range(count)]

    if output_json:
        typer.echo(json.dumps({"names": names}, indent=2))
        return

    for n in names:
        typer.echo(n)
