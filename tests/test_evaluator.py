"""Evaluator + resolver tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from circlelib.runtime.evaluator import EvalError, evaluate
from circlelib.runtime.resolver import CircularImportError, load


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_two_primitives_at_correct_positions(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        scene {
            Sphere(radius=1, position=(1, 2, 3))
            Cube(width=1, height=1, depth=1, position=(-4, 0, 0))
        }
    """)
    nodes = evaluate(load(entry))
    assert len(nodes) == 2
    # pyrr matrices are column-major: translation lives in row 3 cols 0..2.
    assert tuple(nodes[0].transform[3, :3]) == (1.0, 2.0, 3.0)
    assert tuple(nodes[1].transform[3, :3]) == (-4.0, 0.0, 0.0)


def test_color_propagates_to_node(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, "scene { Sphere(radius=1, color=#ff0000) }")
    nodes = evaluate(load(entry))
    assert nodes[0].color == (1.0, 0.0, 0.0)


def test_group_translation_composes_with_child(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        scene {
            Group(position=(10, 0, 0)) {
                Sphere(radius=1, position=(0, 5, 0))
            }
        }
    """)
    nodes = evaluate(load(entry))
    assert len(nodes) == 1
    # Group translates +X by 10, child translates +Y by 5; combined.
    assert tuple(nodes[0].transform[3, :3]) == (10.0, 5.0, 0.0)


def test_component_definition_and_inline_expansion(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        component Twin {
            Sphere(radius=1, position=(-1, 0, 0))
            Sphere(radius=1, position=(1, 0, 0))
        }

        scene {
            Twin(position=(100, 0, 0))
        }
    """)
    nodes = evaluate(load(entry))
    assert len(nodes) == 2
    # Component translates +100, then each child offsets by ±1.
    assert tuple(nodes[0].transform[3, :3]) == (99.0, 0.0, 0.0)
    assert tuple(nodes[1].transform[3, :3]) == (101.0, 0.0, 0.0)


def test_import_resolves_relative_and_alias_works(tmp_path: Path):
    _write(tmp_path / "modules" / "wheels.crl", """
        component Pair {
            Sphere(radius=1, position=(-2, 0, 0))
            Sphere(radius=1, position=(2, 0, 0))
        }
    """)
    entry = tmp_path / "main.crl"
    _write(entry, """
        import "modules/wheels" as wheels

        scene {
            wheels.Pair(position=(0, 5, 0))
        }
    """)
    nodes = evaluate(load(entry))
    assert len(nodes) == 2
    assert tuple(nodes[0].transform[3, :3]) == (-2.0, 5.0, 0.0)
    assert tuple(nodes[1].transform[3, :3]) == (2.0, 5.0, 0.0)


def test_circular_import_is_detected(tmp_path: Path):
    _write(tmp_path / "a.crl", 'import "b" as b\nscene { Sphere(radius=1) }')
    _write(tmp_path / "b.crl", 'import "a" as a\n')
    with pytest.raises(CircularImportError):
        load(tmp_path / "a.crl")


def test_unknown_primitive_raises(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, "scene { Pyramid(size=1) }")
    with pytest.raises(EvalError):
        evaluate(load(entry))


def test_missing_required_arg_raises(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, "scene { Cube(width=1, height=1) }")
    with pytest.raises(EvalError):
        evaluate(load(entry))
