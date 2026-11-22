import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import typer
from godotkit.engine import (
    AssetNotFoundError,
    GodotVersion,
    ReleaseNotFoundError,
    detect_architecture,
    detect_platform,
    utils,
)
from godotkit.exceptions import GodotkitError

from gogo.core import engines

from .shared import (
    print_error,
    print_success,
    print_table,
    print_warning,
)

engine_app = typer.Typer(
    name="engine",
    help="[bold green]Manage Godot engine versions.[/bold green]",
    short_help="Manage engine versions.",
)


def _bool_color(v: bool) -> str:
    return "[green]TRUE[/green]" if v else "[red]FALSE[/red]"


@engine_app.command("list")
def engine_list(
    default: bool = typer.Option(
        False, "--default", help="Highlight the default engine."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Show full installation paths."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """List installed Godot engine versions."""
    versions = engines.list_installed()

    if not versions:
        if output_json:
            typer.echo(json.dumps({"engines": []}))
        else:
            print_warning("No installed engine versions found.")
        return

    default_engine = engines.get_default() if (default or verbose) else None

    if output_json:
        items = []
        for name, path in versions.items():
            entry: dict[str, Any] = {"version": name}
            if default or verbose:
                entry["default"] = path == default_engine
            if verbose:
                entry["binary_path"] = str(utils.find_binary(path))
            items.append(entry)

        typer.echo(json.dumps({"engines": items}, indent=2))
        return

    if verbose:
        rows = []
        for name, path in versions.items():
            rows.append(
                [
                    name,
                    str(utils.find_binary(path)),
                    _bool_color(path == default_engine),
                ]
            )
        print_table(["Version", "Binary Path", "Default"], rows)
    else:
        for name, path in versions.items():
            marker = "* " if path == default_engine else "  "
            typer.echo(f"{marker}{name}")


@engine_app.command("start")
def engine_start(
    version: str | None = typer.Argument(None, help="The engine version to start."),
) -> None:
    """Start a specific installed Godot engine version."""
    if version:
        name = str(_parse_version(version))
        engine_path = engines.list_installed().get(name)
        if not engine_path:
            print_error(f"Godot {name} isn't installed.")
    else:
        engine_path = engines.get_default()
        if not engine_path:
            print_error("No engine version specified and no default engine is set.")
        name = engine_path.name

    binary = utils.find_binary(engine_path)
    if not binary:
        print_error(f"Couldn't find the Godot executable for {name}.")

    typer.echo(f"Starting Godot {name}...")
    utils.start(binary)


def _parse_version(text: str) -> GodotVersion:
    try:
        return GodotVersion.parse(text)
    except ValueError:
        print_error(f"Invalid version: {text}")


@engine_app.command("browse")
def browse(
    all_release_types: bool = typer.Option(
        False, "--all", help="Show all release types."
    ),
    csharp: bool = typer.Option(
        False, "--csharp", help="Filter for C# variant releases."
    ),
    arch: str | None = typer.Option(None, "--arch", help="Filter by architecture."),
    platform_name: str | None = typer.Option(None, "--os", help="Filter by platform."),
    new: bool = typer.Option(False, "--new", help="Refresh cache before listing."),
    max_releases: int = typer.Option(5, "--max", help="Maximum number of releases."),
    output_json: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    """Browse remote Godot releases with filters."""
    plat = platform_name or detect_platform()
    arch = arch or detect_architecture()

    with engines.fetcher() as fetcher:
        try:
            releases = fetcher.fetch_releases(
                stable_only=not all_release_types,
                max_releases=max_releases,
                platform=plat,
                arch=arch,
                refresh_cache=new,
            )
        except ValueError as e:
            print_error(str(e))

    if not releases:
        print_warning("No matching releases found.")
        raise typer.Exit()

    rows = []
    for release in releases:
        asset = release.get_asset(plat, arch, csharp)
        version_name = str(replace(release.version, csharp_enabled=csharp))
        rows.append((version_name, release.tag, release.published_at, asset))

    if output_json:
        items = [
            {
                "version": name,
                "tag": tag,
                "published": published.isoformat(),
                "url": asset.url if asset else None,
            }
            for name, tag, published, asset in rows
        ]
        typer.echo(json.dumps({"releases": items}, indent=2))
        return

    print_table(
        ["Version", "Tag", "Published", "Download URL"],
        [
            [name, tag, f"{published:%Y-%m-%d}", asset.url if asset else "N/A"]
            for name, tag, published, asset in rows
        ],
    )


@engine_app.command("install")
def install(
    version: str = typer.Argument(
        ..., help="A version, e.g. '4.3', '4.4-rc2' or '4.3.stable.mono'."
    ),
    csharp: bool = typer.Option(False, "--csharp", help="Install the C# variant."),
    path: str | None = typer.Option(None, "--path", help="Custom installation path."),
) -> None:
    """Install a specific Godot engine version."""
    target = _parse_version(version)
    if csharp:
        target = replace(target, csharp_enabled=True)

    if path:
        print_warning("Custom installation paths are not tracked.")
    typer.echo(f"Installing Godot {target}...")

    try:
        install_path = engines.install(
            target, target=Path(path).resolve() if path else None
        )
    except ReleaseNotFoundError:
        print_error(f"Couldn't find Godot {target}.")
    except AssetNotFoundError:
        print_error(f"Godot {target} has no build for this computer.")
    except FileExistsError:
        print_error(f"Godot {target} is already installed.")
    except (GodotkitError, OSError) as e:
        print_error(f"Couldn't install Godot {target}: {e}")

    print_success(f"Installed Godot {target} to {install_path}.")


@engine_app.command("default")
def engine_default(
    version: str | None = typer.Argument(
        None, help="The engine version to set as default."
    ),
) -> None:
    """Set or show the default engine version."""
    if not version:
        default_engine = engines.get_default()
        if default_engine:
            typer.echo(f"Default engine: {default_engine.name}")
        else:
            typer.echo("No default engine set.")
        return

    name = str(_parse_version(version))
    engine_path = engines.list_installed().get(name)
    if not engine_path:
        print_error(
            f"Godot {name} isn't installed. Install it with: gogo engine install {name}"
        )

    engines.set_default(engine_path)
    print_success(f"Default engine set to {name}.")
