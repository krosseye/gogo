from pathlib import Path

import pytest

from gogo.core import git


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/user/demo.git",
        "https://github.com/user/demo/",
        "git@github.com:user/demo.git",
        "git@host:demo.git",
    ],
)
def test_clone_returns_existing_folder_untouched(tmp_path: Path, url: str) -> None:
    (tmp_path / "demo").mkdir()
    assert git.clone(url, tmp_path) == tmp_path / "demo"


def test_clone_rejects_url_without_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        git.clone("https://host/.git", tmp_path)
