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


def test_top_level_binding_resolves_in_argument(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        size = 5
        scene { Cube(width=size, height=size, depth=size, position=(0, 0, 0)) }
    """)
    nodes = evaluate(load(entry))
    assert len(nodes) == 1
    # No way to read scalar args off SceneNode directly, but we can check
    # the cube vertex bounds — primitives.cube spans ±width/2 along X.
    xs = nodes[0].vertices[:, 0]
    assert float(xs.max() - xs.min()) == 5.0


def test_arithmetic_evaluates_in_argument(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        size = 2
        scene { Cube(width=size * 3, height=1, depth=1, position=(0, 0, 0)) }
    """)
    nodes = evaluate(load(entry))
    xs = nodes[0].vertices[:, 0]
    assert float(xs.max() - xs.min()) == 6.0


def test_tuple_component_arithmetic_in_position(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        scene {
            Sphere(radius=1, position=(0, 0, 0) + (1, 2, 3))
        }
    """)
    nodes = evaluate(load(entry))
    assert tuple(nodes[0].transform[3, :3]) == (1.0, 2.0, 3.0)


def test_unary_minus_in_argument(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        offset = 4
        scene {
            Sphere(radius=1, position=(-offset, 0, 0))
        }
    """)
    nodes = evaluate(load(entry))
    assert tuple(nodes[0].transform[3, :3]) == (-4.0, 0.0, 0.0)


def test_component_local_binding_is_visible_in_body(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        component Stack {
            step = 2
            Sphere(radius=1, position=(0, step * 0, 0))
            Sphere(radius=1, position=(0, step * 1, 0))
            Sphere(radius=1, position=(0, step * 2, 0))
        }

        scene {
            Stack(position=(0, 0, 0))
        }
    """)
    nodes = evaluate(load(entry))
    ys = [tuple(n.transform[3, :3])[1] for n in nodes]
    assert ys == [0.0, 2.0, 4.0]


def test_undefined_identifier_raises(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, "scene { Cube(width=missing, height=1, depth=1) }")
    with pytest.raises(EvalError):
        evaluate(load(entry))


def test_module_binding_does_not_leak_into_imported_module(tmp_path: Path):
    _write(tmp_path / "modules" / "ext.crl", """
        component Marker {
            Sphere(radius=1, position=(host_size, 0, 0))
        }
    """)
    entry = tmp_path / "main.crl"
    _write(entry, """
        host_size = 7
        import "modules/ext" as ext

        scene {
            ext.Marker(position=(0, 0, 0))
        }
    """)
    # ext.crl never declared `host_size`; the entry module's binding
    # must not leak across modules.
    with pytest.raises(EvalError):
        evaluate(load(entry))


def test_division_by_zero_raises(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, "scene { Cube(width=1 / 0, height=1, depth=1) }")
    with pytest.raises(EvalError):
        evaluate(load(entry))


def test_plane_renders_with_translation(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        scene {
            Plane(width=10, depth=6, position=(0, 0, 0), color=#222222)
            Plane(width=4, depth=4, position=(5, 1, -2))
        }
    """)
    nodes = evaluate(load(entry))
    assert len(nodes) == 2
    # Plane mesh is 4 vertices in the XZ plane (y=0).
    assert nodes[0].vertices.shape == (4, 3)
    assert np.allclose(nodes[0].vertices[:, 1], 0.0)
    # Width spans x in [-5, 5], depth spans z in [-3, 3].
    xs = sorted(set(nodes[0].vertices[:, 0].tolist()))
    zs = sorted(set(nodes[0].vertices[:, 2].tolist()))
    assert xs == [-5.0, 5.0]
    assert zs == [-3.0, 3.0]
    # Normals point +Y.
    assert np.allclose(nodes[0].normals, np.array([[0.0, 1.0, 0.0]] * 4))
    # Translation applies to the second plane.
    assert tuple(nodes[1].transform[3, :3]) == (5.0, 1.0, -2.0)
    # Default color falls back when omitted.
    assert nodes[1].color == pytest.approx((0.85, 0.85, 0.9))


def test_cone_apex_and_base_geometry(tmp_path: Path):
    entry = tmp_path / "main.crl"
    _write(entry, """
        scene {
            Cone(radius=2, height=5, position=(3, 0, 0), color=#ff8800)
        }
    """)
    nodes = evaluate(load(entry))
    assert len(nodes) == 1
    node = nodes[0]
    # Translation lands on the cone's local origin (base centre).
    assert tuple(node.transform[3, :3]) == (3.0, 0.0, 0.0)

    ys = node.vertices[:, 1]
    # Apex sits at y == height; base ring + base centre sit at y == 0.
    assert float(ys.max()) == pytest.approx(5.0)
    assert float(ys.min()) == pytest.approx(0.0)

    # Base ring radius should be `radius`.
    base_xz = node.vertices[ys == 0.0][:, [0, 2]]
    radii = np.sqrt(np.sum(base_xz ** 2, axis=1))
    assert radii.max() == pytest.approx(2.0, abs=1e-5)

    # Side normals must have a positive Y component (slanted outward+up).
    apex_normals = node.normals[ys == 5.0]
    assert np.all(apex_normals[:, 1] > 0.0)
    # Side normals should be unit length.
    side_lens = np.linalg.norm(apex_normals, axis=1)
    assert np.allclose(side_lens, 1.0, atol=1e-5)
