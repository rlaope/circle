"""glTF 2.0 + Three.js viewer emitter.

`export_threejs(scene, out_dir)` walks the static frame of a
`CompiledScene` and writes:

  out_dir/
  ├── scene.gltf         glTF 2.0 JSON (references scene.bin or
  │                      embeds it as base64 when `embed=True`).
  ├── scene.bin          binary buffer with all vertex / normal /
  │                      index data (omitted in `embed=True` mode).
  └── index.html         a tiny self-contained Three.js viewer that
                         loads scene.gltf via OrbitControls.

Animation export (glTF channels driven by the scene's `animate { }`
rules) is a stretch goal not yet implemented — only the t = 0 static
frame is emitted in v0.4.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from circlelib.runtime.evaluator import CompiledScene, SceneNode


_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "viewer.html"


_GLTF_BUFFER_TARGET_ARRAY_BUFFER = 34962          # ARRAY_BUFFER
_GLTF_BUFFER_TARGET_ELEMENT_ARRAY_BUFFER = 34963  # ELEMENT_ARRAY_BUFFER
_GLTF_COMPONENT_FLOAT = 5126
_GLTF_COMPONENT_UNSIGNED_INT = 5125


def export_threejs(
    scene: CompiledScene,
    out_dir: str | Path,
    *,
    embed: bool = False,
    time: float = 0.0,
) -> Path:
    """Write a Three.js / glTF viewer at `out_dir`.

    Parameters
    ----------
    scene
        Compiled scene returned from ``compile_program(program)``.
    out_dir
        Directory to write into. Created if it does not exist.
    embed
        If True, the binary buffer is base64-inlined inside
        ``scene.gltf`` and ``scene.bin`` is not written. Useful for
        sharing a single self-contained file.
    time
        The frame time used for the static export. Defaults to 0.0.

    Returns
    -------
    Path
        The output directory.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    nodes = scene(time)
    gltf, big_buffer = _build_gltf(nodes)

    if embed:
        b64 = base64.b64encode(big_buffer).decode("ascii")
        gltf["buffers"][0]["uri"] = (
            f"data:application/octet-stream;base64,{b64}"
        )
    else:
        bin_path = out / "scene.bin"
        bin_path.write_bytes(big_buffer)
        gltf["buffers"][0]["uri"] = "scene.bin"

    (out / "scene.gltf").write_text(
        json.dumps(gltf, indent=2), encoding="utf-8"
    )
    (out / "index.html").write_text(
        _TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return out


def _build_gltf(nodes: List[SceneNode]) -> Tuple[Dict[str, Any], bytes]:
    """Build a glTF JSON dict + concatenated binary buffer from nodes."""
    binary_chunks: List[bytes] = []
    buffer_views: List[Dict[str, Any]] = []
    accessors: List[Dict[str, Any]] = []
    materials: List[Dict[str, Any]] = []
    meshes: List[Dict[str, Any]] = []
    gltf_nodes: List[Dict[str, Any]] = []

    offset = 0

    def _append_view(byte_data: bytes, target: int) -> int:
        nonlocal offset
        view_index = len(buffer_views)
        binary_chunks.append(byte_data)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(byte_data),
                "target": target,
            }
        )
        offset += len(byte_data)
        return view_index

    for node in nodes:
        verts = node.vertices.astype("f4")
        norms = node.normals.astype("f4")
        idx = node.indices.astype("u4")

        pos_view = _append_view(verts.tobytes(), _GLTF_BUFFER_TARGET_ARRAY_BUFFER)
        nrm_view = _append_view(norms.tobytes(), _GLTF_BUFFER_TARGET_ARRAY_BUFFER)
        idx_view = _append_view(
            idx.tobytes(), _GLTF_BUFFER_TARGET_ELEMENT_ARRAY_BUFFER
        )

        # POSITION must publish min/max bounds per the glTF spec.
        pos_min = verts.min(axis=0).astype(float).tolist()
        pos_max = verts.max(axis=0).astype(float).tolist()

        pos_acc = _append_accessor(
            accessors, pos_view, _GLTF_COMPONENT_FLOAT, len(verts), "VEC3",
            mn=pos_min, mx=pos_max,
        )
        nrm_acc = _append_accessor(
            accessors, nrm_view, _GLTF_COMPONENT_FLOAT, len(norms), "VEC3",
        )
        idx_acc = _append_accessor(
            accessors, idx_view, _GLTF_COMPONENT_UNSIGNED_INT, len(idx), "SCALAR",
        )

        mat_idx = len(materials)
        materials.append(
            {
                "pbrMetallicRoughness": {
                    "baseColorFactor": [
                        float(node.color[0]),
                        float(node.color[1]),
                        float(node.color[2]),
                        float(node.alpha),
                    ],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.7,
                },
                "doubleSided": False,
            }
        )

        mesh_idx = len(meshes)
        meshes.append(
            {
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": pos_acc,
                            "NORMAL": nrm_acc,
                        },
                        "indices": idx_acc,
                        "material": mat_idx,
                    }
                ]
            }
        )

        # SceneNode.transform uses the same byte layout as OpenGL
        # column-major mat4. flatten(order='C') reproduces that byte
        # order, which is exactly what glTF expects in its `matrix`
        # field (column-major float[16]).
        matrix_floats = node.transform.astype("f4").flatten(order="C").tolist()
        gltf_nodes.append({"mesh": mesh_idx, "matrix": matrix_floats})

    big_buffer = b"".join(binary_chunks)
    gltf: Dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "circlelib export"},
        "buffers": [{"byteLength": len(big_buffer)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "materials": materials,
        "meshes": meshes,
        "nodes": gltf_nodes,
        "scenes": [{"nodes": list(range(len(gltf_nodes)))}],
        "scene": 0,
    }
    return gltf, big_buffer


def _append_accessor(
    accessors: List[Dict[str, Any]],
    buffer_view: int,
    component_type: int,
    count: int,
    type_: str,
    *,
    mn: Optional[List[float]] = None,
    mx: Optional[List[float]] = None,
) -> int:
    accessor: Dict[str, Any] = {
        "bufferView": buffer_view,
        "componentType": component_type,
        "count": count,
        "type": type_,
    }
    if mn is not None:
        accessor["min"] = mn
    if mx is not None:
        accessor["max"] = mx
    idx = len(accessors)
    accessors.append(accessor)
    return idx
