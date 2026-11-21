import json
import time
from pathlib import Path
from typing import Any

import typer
from godotkit.engine import GodotVersion, utils
from godotkit.engine.release_fetcher import (
    GodotFetcher,
    detect_architecture,
    detect_platform,
)

from gogo.core import engines, paths

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
    default_name = default_engine.name if default_engine else None

    if output_json:
        items = []
        for name, path in versions.items():
            entry: dict[str, Any] = {"version": name}
            if default or verbose:
                entry["default"] = name == default_name
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
                    _bool_color(name == default_name),
                ]
            )
        print_table(["Version", "Binary Path", "Default"], rows)
    else:
        for name in versions:
            marker = "* " if name == default_name else "  "
            typer.echo(f"{marker}{name}")


@engine_app.command("start")
def engine_start(
    version: str | None = typer.Argument(None, help="The engine version to start."),
) -> None:
    """Start a specific installed Godot engine version."""
    default_engine = engines.get_default()
    target = version or (default_engine.name if default_engine else None)

    if not target:
        print_error("No engine version specified and no default engine is set.")

    try:
        parsed = str(GodotVersion.parse(target))
    except ValueError:
        print_error(f"Invalid version: {target}")

    engine_path = paths.versions_dir() / parsed
    if not engine_path.exists():
        print_error(f"Engine version not found: {parsed}")

    binary = utils.find_binary(engine_path)
    if not binary:
        print_error(f"No engine binary found for version: {parsed}")

    print_success(f"Starting Godot {parsed}.")
    utils.start(binary)


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
    fetcher = GodotFetcher()
    plat = platform_name or detect_platform()
    arch = arch or detect_architecture()

    releases = fetcher.fetch_releases(
        stable_only=not all_release_types,
        max_releases=max_releases,
        platform_only=True,
        refresh_cache=new,
    )

    if not releases:
        print_warning("No matching releases found.")
        raise typer.Exit()

    if output_json:
        items = []
        for release in releases:
            asset = release.get_asset(plat, arch, csharp)
            items.append(
                {
                    "version": str(GodotVersion.from_url(asset.url)) if asset else None,
                    "tag": release.version,
                    "published": release.published_at.isoformat(),
                    "url": asset.url if asset else None,
                }
            )
        typer.echo(json.dumps({"releases": items}, indent=2))
        return

    rows = []
    for release in releases:
        asset = release.get_asset(plat, arch, csharp)
        version_str = "N/A" if not asset else str(GodotVersion.from_url(asset.url))
        url = "N/A" if not asset else asset.url
        rows.append(
            [
                version_str,
                release.version,
                release.published_at.strftime("%Y-%m-%d"),
                url,
            ]
        )

    print_table(["Version", "Tag", "Published", "Download URL"], rows)


@engine_app.command("install")
def install(
    tag: str = typer.Argument(..., help="A release tag (e.g., '4.2.3-stable')."),
    csharp: bool = typer.Option(False, "--csharp", help="Install the C# variant."),
    path: str | None = typer.Option(None, "--path", help="Custom installation path."),
) -> None:
    """Install a specific Godot engine version."""
    from godotkit.engine import DownloadError, ExtractError

    base_version = tag.split("-")[0]
    print_success(f"Searching for Godot {base_version}.")

    fetcher = GodotFetcher()

    download_url: str | None = None
    max_releases = 5
    increment = 5
    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            fetcher.fetch_releases(
                stable_only=tag.endswith("-stable"),
                max_releases=max_releases,
                refresh_cache=True,
            )
            download_url = fetcher.get_download_url(tag, mono=csharp)
            break
        except ValueError:
            max_releases += increment
            print_warning(
                f"Version not found. Expanding search to {max_releases} releases."
            )
            time.sleep(1 + attempt)

    if not download_url:
        print_error(f"Could not find engine version {tag}.")

    typer.echo(f"Downloading from: {download_url}")

    install_path = Path(
        path or (paths.versions_dir() / str(GodotVersion.from_url(download_url)))
    ).resolve()

    if path:
        print_warning("Custom installation paths are not tracked.")

    try:
        utils.download_and_extract(download_url, install_path)
    except (DownloadError, ExtractError) as e:
        print_error(f"{e}")
    except Exception as e:
        print_error(f"{type(e).__name__}: {e}")

    print_success("Installation completed.")


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

    try:
        parsed = str(GodotVersion.parse(version))
    except ValueError:
        print_error(f"Invalid version: {version}")

    versions = engines.list_installed()
    if parsed not in versions:
        print_error(f"Engine version not found: {parsed}. Maybe install it first?")

    engines.set_default(paths.versions_dir() / parsed)
    print_success(f"Default engine set to {parsed}.")
