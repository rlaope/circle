"""Offscreen rendering — produces a PNG without opening a window.

Used by `circlelib run scene.crl --export-png out.png`. Builds a
ModernGL standalone context, attaches an off-screen framebuffer, runs
one frame through the same `Renderer` used by the windowed path, reads
the framebuffer, and writes the file via Pillow.

The standalone context is platform-dependent (macOS CGL, Linux EGL);
``RuntimeError`` is raised if it cannot be created.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import moderngl
from PIL import Image

from circlelib.render.camera import OrbitCamera
from circlelib.render.renderer import Renderer
from circlelib.runtime.evaluator import SceneNode


def render_to_png(
    nodes: List[SceneNode],
    out_path: str | Path,
    *,
    width: int = 960,
    height: int = 720,
) -> Path:
    """Render `nodes` once into a PNG at `out_path`.

    Returns the resolved Path of the written file. Camera defaults
    match the windowed orbit camera (yaw 35°, pitch 25°, radius 18).
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    try:
        ctx = moderngl.create_standalone_context()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "could not create a standalone OpenGL context for offscreen "
            "rendering — install a working GL driver or run with a display"
        ) from exc

    try:
        color_tex = ctx.texture((width, height), 4)
        depth_tex = ctx.depth_texture((width, height))
        fbo = ctx.framebuffer(
            color_attachments=[color_tex], depth_attachment=depth_tex
        )
        fbo.use()
        ctx.viewport = (0, 0, width, height)

        renderer = Renderer(ctx)
        renderer.upload(nodes)

        camera = OrbitCamera()
        view = camera.view_matrix()
        proj = camera.projection_matrix(width / height)
        renderer.draw(view, proj)

        data = fbo.read(components=3, alignment=1)
        # GL framebuffer origin is bottom-left; PNG convention is
        # top-left, so flip vertically before writing.
        img = Image.frombytes("RGB", (width, height), data)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        out = Path(out_path)
        img.save(out, "PNG")
        return out
    finally:
        ctx.release()
