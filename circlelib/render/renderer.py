"""ModernGL renderer.

Builds a VBO + IBO + VAO per SceneNode once, then draws them every
frame with a single Lambert-shaded shader program. The camera supplies
view + projection. The light is a fixed directional light from above.
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


@dataclass
class _GpuMesh:
    vao: moderngl.VertexArray
    transform: np.ndarray
    color: tuple


class Renderer:
    def __init__(self, ctx: moderngl.Context) -> None:
        self.ctx = ctx
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.program = ctx.program(
            vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER
        )
        self._meshes: List[_GpuMesh] = []

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

    def draw(self, view: np.ndarray, proj: np.ndarray) -> None:
        # Black background.
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.program["u_view"].write(view.astype("f4").tobytes())
        self.program["u_proj"].write(proj.astype("f4").tobytes())
        self.program["u_light_dir"].value = (-0.4, -1.0, -0.3)
        for mesh in self._meshes:
            self.program["u_model"].write(mesh.transform.astype("f4").tobytes())
            self.program["u_color"].value = mesh.color
            mesh.vao.render()
