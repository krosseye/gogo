from pathlib import Path

import pytest
from godotkit.engine import GodotVersion, ReleaseNotFoundError

from gogo.core import engines

NET_4_3 = GodotVersion(4, 3, csharp_enabled=True)


@pytest.fixture
def versions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(engines.paths, "versions_dir", lambda: tmp_path)
    return tmp_path


def test_list_installed_keys_by_canonical_name(versions_dir: Path) -> None:
    (versions_dir / "4.3.stable.mono").mkdir()
    (versions_dir / "4.4.rc2").mkdir()
    (versions_dir / "not a version").mkdir()

    assert engines.list_installed() == {
        "4.4.rc2": versions_dir / "4.4.rc2",
        "4.3.stable.mono": versions_dir / "4.3.stable.mono",
    }
    assert engines.install_dir(NET_4_3) == versions_dir / "4.3.stable.mono"


def test_find_asset_refreshes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, bool]] = []

    class StaleFetcher:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def find_asset(self, version):
            if not calls:
                raise ReleaseNotFoundError("stale cache")
            return "asset"

        def fetch_releases(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(engines, "fetcher", StaleFetcher)

    assert engines.find_asset(NET_4_3) == "asset"
    assert calls == [{"stable_only": False, "refresh_cache": True}]
