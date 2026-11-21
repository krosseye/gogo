from pathlib import Path

import pytest

from gogo.core import projects


@pytest.fixture
def projects_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    file = tmp_path / "projects.json"
    monkeypatch.setattr(projects.paths, "projects_file", lambda: file)
    return file


def test_add_favourite_remove_roundtrip(projects_file: Path, tmp_path: Path) -> None:
    folder = tmp_path / "game"
    projects.add(folder / projects.PROJECT_FILE)
    projects.add(folder)
    projects.set_favourite(folder, True)

    [entry] = projects.load()
    assert entry.path == folder.resolve()
    assert projects.is_favourite(folder)

    projects.remove(folder)
    assert projects.load() == []


def test_corrupt_list_is_kept_aside(projects_file: Path) -> None:
    projects_file.write_text("{not json", encoding="utf-8")

    assert projects.load() == []
    assert not projects_file.exists()
    [backup] = projects_file.parent.glob("projects.json.corrupt-*")
    assert backup.read_text(encoding="utf-8") == "{not json"
