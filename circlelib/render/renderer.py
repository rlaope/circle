"""ModernGL renderer.

Builds a VBO + IBO + VAO per SceneNode once, then draws them every
frame with a single Lambert-shaded shader program. The camera supplies
view + projection. The light is a fixed directional light from above.

A separate line program draws an always-on Matrix-style ground grid
(plus the X/Y/Z axes) so the viewer can perceive depth and orientation
even before any scene content is added.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import moderngl
import numpy as np

from circlelib.runtime.evaluator import SceneNode


VERTEX_SHADER = """
#version 330

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_proj;

in vec3 in_position;
in vec3 in_normal;

out vec3 v_normal;

void main() {
    vec4 world = u_model * vec4(in_position, 1.0);
    gl_Position = u_proj * u_view * world;

    // Rotate normals into world space (assuming uniform scale).
    v_normal = normalize(mat3(u_model) * in_normal);
}
"""

FRAGMENT_SHADER = """
#version 330

uniform vec3 u_color;
uniform vec3 u_light_dir;

in vec3 v_normal;
out vec4 frag_color;

void main() {
    float diffuse = max(dot(normalize(v_normal), normalize(-u_light_dir)), 0.0);
    float ambient = 0.25;
    vec3 shaded = u_color * (ambient + (1.0 - ambient) * diffuse);
    frag_color = vec4(shaded, 1.0);
}
"""


LINE_VERTEX_SHADER = """
#version 330
uniform mat4 u_view;
uniform mat4 u_proj;
in vec3 in_position;
in vec3 in_color;
out vec3 v_color;
void main() {
    gl_Position = u_proj * u_view * vec4(in_position, 1.0);
    v_color = in_color;
}
"""


LINE_FRAGMENT_SHADER = """
#version 330
in vec3 v_color;
out vec4 frag_color;
void main() {
    frag_color = vec4(v_color, 1.0);
}
"""


def _build_grid_buffer(
    extent: int = 20,
    grid_color=(0.0, 0.55, 0.4),
    axis_x_color=(1.0, 0.25, 0.35),
    axis_y_color=(0.45, 1.0, 0.55),
    axis_z_color=(0.35, 0.6, 1.0),
) -> np.ndarray:
    """Returns interleaved (position, color) line vertices for the Matrix
    ground grid plus the three world axes. Two vertices per line."""
    rows: list[tuple[float, float, float, float, float, float]] = []
    n = extent
    for i in range(-n, n + 1):
        if i == 0:
            continue  # axes drawn separately in their own colors
        rows.append((-n, 0.0, float(i), *grid_color))
        rows.append(( n, 0.0, float(i), *grid_color))
        rows.append((float(i), 0.0, -n, *grid_color))
        rows.append((float(i), 0.0,  n, *grid_color))

    # World axes through the origin, slightly above the grid plane to
    # avoid z-fighting at y=0.
    rows.append((-n, 0.001, 0.0, *axis_x_color))
    rows.append(( n, 0.001, 0.0, *axis_x_color))
    rows.append((0.0, 0.001, -n, *axis_z_color))
    rows.append((0.0, 0.001,  n, *axis_z_color))
    rows.append((0.0, 0.0, 0.0, *axis_y_color))
    rows.append((0.0, float(n) * 0.4, 0.0, *axis_y_color))

    return np.array(rows, dtype="f4")


@dataclass
class _GpuMesh:
    vao: moderngl.VertexArray
    transform: np.ndarray
    color: tuple


class Renderer:
    def __init__(self, ctx: moderngl.Context, *, show_grid: bool = True) -> None:
        self.ctx = ctx
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.program = ctx.program(
            vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER
        )
        self._meshes: List[_GpuMesh] = []

        self._grid_program = None
        self._grid_vao = None
        self._grid_count = 0
        if show_grid:
            self._grid_program = ctx.program(
                vertex_shader=LINE_VERTEX_SHADER,
                fragment_shader=LINE_FRAGMENT_SHADER,
            )
            grid = _build_grid_buffer()
            self._grid_count = grid.shape[0]
            grid_vbo = ctx.buffer(grid.tobytes())
            self._grid_vao = ctx.vertex_array(
                self._grid_program,
                [(grid_vbo, "3f 3f", "in_position", "in_color")],
            )

    def upload(self, nodes: List[SceneNode]) -> None:
        for mesh in self._meshes:
            mesh.vao.release()
        self._meshes.clear()
        for node in nodes:
            interleaved = np.hstack(
                [node.vertices.astype("f4"), node.normals.astype("f4")]
            )
            vbo = self.ctx.buffer(interleaved.tobytes())
            ibo = self.ctx.buffer(node.indices.astype("u4").tobytes())
            vao = self.ctx.vertex_array(
                self.program,
                [(vbo, "3f 3f", "in_position", "in_normal")],
                ibo,
            )
            self._meshes.append(
                _GpuMesh(vao=vao, transform=node.transform, color=node.color)
            )

    def update(self, nodes: List[SceneNode]) -> None:
        """Per-frame refresh of transforms / colors only.

        Falls back to a full re-upload if the node count changes
        (shouldn't happen in v0.3 — animations only mutate
        position/rotation/color, never topology).
        """
        if len(nodes) != len(self._meshes):
            self.upload(nodes)
            return
        for mesh, node in zip(self._meshes, nodes):
            mesh.transform = node.transform
            mesh.color = node.color

    def draw(self, view: np.ndarray, proj: np.ndarray) -> None:
        # Black background.
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        # Matrix grid first so meshes can occlude it correctly.
        if self._grid_vao is not None:
            self._grid_program["u_view"].write(view.astype("f4").tobytes())
            self._grid_program["u_proj"].write(proj.astype("f4").tobytes())
            self._grid_vao.render(mode=moderngl.LINES, vertices=self._grid_count)

        self.program["u_view"].write(view.astype("f4").tobytes())
        self.program["u_proj"].write(proj.astype("f4").tobytes())
        self.program["u_light_dir"].value = (-0.4, -1.0, -0.3)
        for mesh in self._meshes:
            self.program["u_model"].write(mesh.transform.astype("f4").tobytes())
            self.program["u_color"].value = mesh.color
            mesh.vao.render()
