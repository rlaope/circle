"""Tests for the third-party package cache and `circlelib install`.

Network is never touched: `install_from_local` is enough to validate
the resolver path. `CIRCLELIB_HOME` is overridden per test so the real
user cache (`~/.circlelib`) is left alone.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from circlelib.parser import parse_file
from circlelib.runtime.evaluator import compile_program
from circlelib.runtime.installer import (
    InstallError,
    install_from_local,
    list_installed,
    parse_slug,
)
from circlelib.runtime.resolver import (
    PackageNotInstalledError,
    circlelib_home,
    load,
    packages_root,
)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Redirect `CIRCLELIB_HOME` to an isolated tmp dir for this test."""
    home = tmp_path / "circlelib_home"
    monkeypatch.setenv("CIRCLELIB_HOME", str(home))
    return home


def _write_pkg(root: Path) -> Path:
    """Materialise a tiny `@me/pkg/widget` package on disk and return root."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "widget.crl").write_text(
        textwrap.dedent(
            """
            component Widget {
                Cube(width=1, height=1, depth=1, position=(0, 0.5, 0), color=#ff5577)
                Sphere(radius=0.4, position=(0, 1.4, 0), color=#3aa0ff)
            }
            """
        ).strip()
    )
    return root


def test_circlelib_home_honours_env(cache, tmp_path):
    assert circlelib_home() == cache.resolve()
    assert packages_root() == (cache / "packages").resolve()


def test_install_from_local_copies_files(cache, tmp_path):
    src = _write_pkg(tmp_path / "src")
    pkg = install_from_local("me", "pkg", src)

    assert pkg.path == (cache / "packages" / "me" / "pkg").resolve()
    assert (pkg.path / "widget.crl").is_file()


def test_install_overwrites_existing(cache, tmp_path):
    src1 = _write_pkg(tmp_path / "src1")
    install_from_local("me", "pkg", src1)
    # Replace with a different content.
    src2 = tmp_path / "src2"
    src2.mkdir()
    (src2 / "widget.crl").write_text(
        "component Widget { Cube(width=2, height=2, depth=2, color=#000000) }"
    )
    install_from_local("me", "pkg", src2)
    final = (cache / "packages" / "me" / "pkg" / "widget.crl").read_text()
    assert "width=2" in final


def test_list_installed_yields_each_owner_repo(cache, tmp_path):
    install_from_local("me", "pkg", _write_pkg(tmp_path / "a"))
    install_from_local("you", "lib", _write_pkg(tmp_path / "b"))
    seen = sorted((p.owner, p.repo) for p in list_installed())
    assert seen == [("me", "pkg"), ("you", "lib")]


def test_third_party_prefix_resolves(cache, tmp_path):
    install_from_local("me", "pkg", _write_pkg(tmp_path / "src"))

    entry = tmp_path / "scene.crl"
    entry.write_text(
        textwrap.dedent(
            """
            import "@me/pkg/widget" as w
            scene {
                w.Widget(position=(0, 0, 0))
            }
            """
        ).strip()
    )
    program = load(entry)
    nodes = compile_program(program)(0.0)
    # Widget = 1 cube + 1 sphere = 2 leaves.
    assert len(nodes) == 2


def test_missing_package_error_points_at_install_command(cache, tmp_path):
    entry = tmp_path / "scene.crl"
    entry.write_text(
        textwrap.dedent(
            """
            import "@nope/nope/foo" as foo
            scene {
                foo.Foo(position=(0, 0, 0))
            }
            """
        ).strip()
    )
    with pytest.raises(PackageNotInstalledError) as exc:
        load(entry)
    msg = str(exc.value)
    assert "circlelib install nope/nope" in msg


def test_three_import_styles_in_one_user_file(cache, tmp_path):
    install_from_local("me", "pkg", _write_pkg(tmp_path / "src"))

    (tmp_path / "local.crl").write_text(
        "component Local { Sphere(radius=0.5, position=(0, 0, 0), color=#fff) }"
    )
    entry = tmp_path / "scene.crl"
    entry.write_text(
        textwrap.dedent(
            """
            import "local"                    as me
            import "@stdlib/geometry/axes"    as ax
            import "@me/pkg/widget"           as w
            scene {
                me.Local(position=(-2, 0, 0))
                ax.Axes(position=(0, 0, 0))
                w.Widget(position=(2, 0, 0))
            }
            """
        ).strip()
    )
    program = load(entry)
    nodes = compile_program(program)(0.0)
    # Local (1) + Axes (3 cylinders + 1 sphere = 4) + Widget (2) = 7.
    assert len(nodes) == 7


def test_parse_slug_rejects_garbage():
    with pytest.raises(InstallError):
        parse_slug("notaslug")
    with pytest.raises(InstallError):
        parse_slug("a/b/c")
    with pytest.raises(InstallError):
        parse_slug("a/")
    assert parse_slug("me/pkg") == ("me", "pkg")


def test_invalid_third_party_import_path(cache, tmp_path):
    entry = tmp_path / "scene.crl"
    entry.write_text(
        textwrap.dedent(
            """
            import "@me/pkg" as p
            scene { p.Foo(position=(0, 0, 0)) }
            """
        ).strip()
    )
    with pytest.raises(PackageNotInstalledError):
        load(entry)
