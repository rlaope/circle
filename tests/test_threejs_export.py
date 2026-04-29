"""Tests for the glTF / Three.js exporter."""

from __future__ import annotations

import json
from pathlib import Path

from circlelib.exporters.threejs import export_threejs
from circlelib.runtime.evaluator import compile_program
from circlelib.runtime.resolver import load


def _scene(tmp_path: Path, src: str):
    crl = tmp_path / "scene.crl"
    crl.write_text(src, encoding="utf-8")
    return compile_program(load(crl))


def _read_gltf(out: Path) -> dict:
    with (out / "scene.gltf").open() as f:
        return json.load(f)


def test_export_writes_gltf_bin_and_html(tmp_path: Path):
    out = tmp_path / "site"
    scene = _scene(tmp_path, """
        scene { Cube(width=1, height=1, depth=1, color=red) }
    """)
    export_threejs(scene, out)
    assert (out / "scene.gltf").exists()
    assert (out / "scene.bin").exists()
    assert (out / "index.html").exists()
    gltf = _read_gltf(out)
    assert gltf["asset"]["version"] == "2.0"
    assert gltf["buffers"][0]["uri"] == "scene.bin"
    assert (out / "scene.bin").stat().st_size == gltf["buffers"][0]["byteLength"]


def test_export_embed_inlines_buffer_skips_bin(tmp_path: Path):
    out = tmp_path / "site"
    scene = _scene(tmp_path, """
        scene { Sphere(radius=1, color=#ff5577) }
    """)
    export_threejs(scene, out, embed=True)
    gltf = _read_gltf(out)
    assert gltf["buffers"][0]["uri"].startswith(
        "data:application/octet-stream;base64,"
    )
    assert not (out / "scene.bin").exists()


def test_export_emits_one_node_per_leaf_with_matrix(tmp_path: Path):
    out = tmp_path / "site"
    scene = _scene(tmp_path, """
        scene {
            Cube(width=1, height=1, depth=1, position=(0, 0, 0))
            Sphere(radius=1, position=(5, 0, 0))
        }
    """)
    export_threejs(scene, out)
    gltf = _read_gltf(out)
    assert len(gltf["nodes"]) == 2
    assert len(gltf["meshes"]) == 2
    for node in gltf["nodes"]:
        assert "matrix" in node
        assert len(node["matrix"]) == 16
    # Translation component sits in the last 4-float column.
    sphere_matrix = gltf["nodes"][1]["matrix"]
    assert sphere_matrix[12] == 5.0  # tx
    assert sphere_matrix[13] == 0.0  # ty
    assert sphere_matrix[14] == 0.0  # tz
    assert sphere_matrix[15] == 1.0  # w


def test_material_basecolor_uses_node_color_and_alpha(tmp_path: Path):
    out = tmp_path / "site"
    scene = _scene(tmp_path, """
        scene {
            Cube(width=1, height=1, depth=1, color=rgba(255, 0, 0, 0.5))
        }
    """)
    export_threejs(scene, out)
    gltf = _read_gltf(out)
    factor = gltf["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"]
    assert factor == [1.0, 0.0, 0.0, 0.5]


def test_static_scene_export_is_deterministic(tmp_path: Path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    src = "scene { Cube(width=2, height=2, depth=2, color=gold) }"
    scene = _scene(tmp_path, src)
    export_threejs(scene, out_a)
    export_threejs(scene, out_b)
    assert (out_a / "scene.gltf").read_text() == (out_b / "scene.gltf").read_text()
    assert (out_a / "scene.bin").read_bytes() == (out_b / "scene.bin").read_bytes()
