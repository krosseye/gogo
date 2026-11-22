import re
import shutil
import subprocess
from pathlib import Path

CLONE_TIMEOUT = 300


def git_installed() -> bool:
    return shutil.which("git") is not None


def clone(url: str, dest: Path) -> Path:
    """Clone `url` into `dest/<repo name>`. An existing folder is returned untouched.

    Raises:
        ValueError: If no repository name can be taken from `url`.
        RuntimeError: If `git clone` fails or times out.
    """
    # Last path segment of https://host/user/repo.git or git@host:repo.git
    name = re.split(r"[/:\\]", url.rstrip("/"))[-1].removesuffix(".git")
    if not name:
        raise ValueError(f"Can't work out a folder name from {url!r}")

    repo = dest / name
    if repo.exists():
        return repo

    dest.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", url, str(repo)],
            check=True,
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.strip() or f"git clone failed for {url}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"git clone timed out after {CLONE_TIMEOUT}s") from e
    return repo
