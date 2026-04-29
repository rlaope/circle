"""Tests for the @stdlib/ import prefix and the shipped catalog.

Verifies:
- The resolver translates `@stdlib/<sub>` to the package's stdlib dir.
- Every shipped stdlib `.crl` parses cleanly.
- A user scene that imports stdlib evaluates and produces leaves.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from circlelib.parser import parse_file
from circlelib.runtime.evaluator import compile_program
from circlelib.runtime.resolver import STDLIB_ROOT, load


def _stdlib_files():
    return sorted(STDLIB_ROOT.rglob("*.crl"))


# Sanity: the catalog actually shipped with the package.

def test_stdlib_root_exists_and_has_components():
    assert STDLIB_ROOT.is_dir()
    files = _stdlib_files()
    assert len(files) >= 8, f"expected at least 8 stdlib modules, got {len(files)}"


@pytest.mark.parametrize("path", _stdlib_files(), ids=lambda p: str(p.relative_to(STDLIB_ROOT)))
def test_every_stdlib_module_parses(path: Path):
    module = parse_file(path)
    # Stdlib modules are libraries, not entry scenes.
    assert module.scene is None, f"{path}: stdlib modules must not declare a scene block"
    assert len(module.components) >= 1, f"{path}: stdlib module has no components"


def test_stdlib_prefix_resolves_from_a_user_file(tmp_path: Path):
    entry = tmp_path / "demo.crl"
    entry.write_text(
        textwrap.dedent(
            """
            import "@stdlib/furniture/chair" as ch
            scene {
                ch.Chair(position=(0, 0, 0))
            }
            """
        ).strip()
    )
    program = load(entry)
    chair_path = STDLIB_ROOT / "furniture" / "chair.crl"
    assert chair_path.resolve() in program.modules


def test_stdlib_evaluates_to_leaves(tmp_path: Path):
    entry = tmp_path / "demo.crl"
    entry.write_text(
        textwrap.dedent(
            """
            import "@stdlib/vehicles/car" as v
            scene {
                v.Car(position=(0, 0, 0))
            }
            """
        ).strip()
    )
    program = load(entry)
    compiled = compile_program(program)
    nodes = compiled(0.0)
    # Car has body + cabin + 2 headlights + 4 wheels = 8 leaves.
    assert len(nodes) == 8


def test_relative_imports_still_work_alongside_stdlib(tmp_path: Path):
    # A user file that imports both a relative module and a stdlib one.
    (tmp_path / "local.crl").write_text(
        textwrap.dedent(
            """
            component LocalThing {
                Sphere(radius=0.5, position=(0, 0, 0), color=#ffffff)
            }
            """
        ).strip()
    )
    entry = tmp_path / "demo.crl"
    entry.write_text(
        textwrap.dedent(
            """
            import "local"                     as me
            import "@stdlib/geometry/axes"     as ax
            scene {
                me.LocalThing(position=(0, 0, 0))
                ax.Axes(position=(2, 0, 0))
            }
            """
        ).strip()
    )
    program = load(entry)
    assert (tmp_path / "local.crl").resolve() in program.modules
    assert (STDLIB_ROOT / "geometry" / "axes.crl").resolve() in program.modules

    nodes = compile_program(program)(0.0)
    # 1 sphere + Axes (3 cylinders + 1 sphere) = 5 leaves.
    assert len(nodes) == 5
