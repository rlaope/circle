"""Third-party `.crl` package installer.

A package is just a directory of `.crl` files. The installer copies
that directory under `<CIRCLELIB_HOME>/packages/<owner>/<repo>/`, where
the resolver picks it up for `@<owner>/<repo>/...` imports.

Two sources are supported:

- ``install_from_local(owner, repo, src_dir)`` — copy a directory tree
  on disk into the cache. Used both directly and from
  ``circlelib install --from``. Network-free, so test suites use this.
- ``install_from_github(owner, repo, *, upgrade=False)`` — shells out
  to ``git clone`` (or ``git pull`` if ``upgrade=True``) for
  ``https://github.com/<owner>/<repo>.git``. The owner / repo names
  match GitHub's URL slug, so an installed package is identified the
  same way regardless of source.

``list_installed()`` walks the cache and yields ``(owner, repo, path)``
triples.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from circlelib.runtime.resolver import packages_root


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstalledPackage:
    owner: str
    repo: str
    path: Path


def _validate_slug(piece: str, kind: str) -> None:
    if not piece or "/" in piece or piece.startswith(".") or piece.startswith("@"):
        raise InstallError(f"invalid {kind} '{piece}'")


def _target_dir(owner: str, repo: str) -> Path:
    _validate_slug(owner, "owner")
    _validate_slug(repo, "repo")
    return packages_root() / owner / repo


def install_from_local(owner: str, repo: str, src: Path) -> InstalledPackage:
    """Copy `src` (a local directory of `.crl` files) into the cache.

    Overwrites any existing install of the same `<owner>/<repo>` slug.
    """
    src = src.expanduser().resolve()
    if not src.is_dir():
        raise InstallError(f"source directory does not exist: {src}")
    dest = _target_dir(owner, repo)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    return InstalledPackage(owner=owner, repo=repo, path=dest)


def install_from_github(
    owner: str, repo: str, *, upgrade: bool = False
) -> InstalledPackage:
    """Clone (or pull-update) ``https://github.com/<owner>/<repo>.git``.

    Network failures and missing ``git`` raise ``InstallError`` with a
    short, actionable message.
    """
    dest = _target_dir(owner, repo)
    url = f"https://github.com/{owner}/{repo}.git"
    if dest.exists():
        if not upgrade:
            raise InstallError(
                f"'{owner}/{repo}' is already installed at {dest}. "
                f"Pass --upgrade to fetch the latest commits."
            )
        cmd = ["git", "-C", str(dest), "pull", "--ff-only"]
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["git", "clone", "--depth", "1", url, str(dest)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise InstallError(
            "'git' is not on PATH. Install git or use "
            "`circlelib install --from <local-dir> <owner>/<repo>`."
        ) from e
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").strip() or str(e)
        raise InstallError(f"git failed: {msg}") from e
    return InstalledPackage(owner=owner, repo=repo, path=dest)


def list_installed() -> Iterator[InstalledPackage]:
    """Yield every package currently in the cache.

    Walks the two-level layout ``<owner>/<repo>``. Returns an empty
    iterator if the cache directory does not exist yet.
    """
    root = packages_root()
    if not root.is_dir():
        return
    for owner_dir in sorted(root.iterdir()):
        if not owner_dir.is_dir():
            continue
        for repo_dir in sorted(owner_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            yield InstalledPackage(
                owner=owner_dir.name, repo=repo_dir.name, path=repo_dir
            )


def parse_slug(slug: str) -> tuple[str, str]:
    """Parse a CLI ``<owner>/<repo>`` into a tuple. Raises on bad input."""
    parts = slug.split("/")
    if len(parts) != 2 or not all(parts):
        raise InstallError(
            f"expected '<owner>/<repo>' (got '{slug}'). "
            f"Example: 'rlaope/circle-extras'."
        )
    return parts[0], parts[1]
