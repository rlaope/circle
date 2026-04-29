"""Offscreen rendering — produces a PNG (or an MP4 / PNG sequence)
without opening a window.

Used by:

- ``circlelib run scene.crl --export-png out.png`` → ``render_to_png``
- ``circlelib record scene.crl --out clip.mp4``    → ``record_animation``

Both paths build a ModernGL standalone context, attach an off-screen
framebuffer, run one frame (or a frame sequence) through the same
``Renderer`` used by the windowed path, and read pixels back. PNGs are
written via Pillow; the MP4 path pipes raw RGB frames into ``ffmpeg``.

The standalone context is platform-dependent (macOS CGL, Linux EGL);
``RuntimeError`` is raised if it cannot be created.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import moderngl
import numpy as np
from PIL import Image

from circlelib.render.camera import OrbitCamera
from circlelib.render.renderer import Renderer
from circlelib.runtime.evaluator import CompiledScene, SceneNode


class FfmpegMissingError(RuntimeError):
    """Raised when ffmpeg is not on PATH and the caller asked for MP4."""


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


def _build_offscreen(width: int, height: int):
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    try:
        ctx = moderngl.create_standalone_context()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "could not create a standalone OpenGL context for offscreen "
            "rendering — install a working GL driver or run with a display"
        ) from exc
    color_tex = ctx.texture((width, height), 4)
    depth_tex = ctx.depth_texture((width, height))
    fbo = ctx.framebuffer(color_attachments=[color_tex], depth_attachment=depth_tex)
    fbo.use()
    ctx.viewport = (0, 0, width, height)
    return ctx, fbo


def _read_rgb_flipped(fbo, width: int, height: int) -> bytes:
    """Read RGB framebuffer and flip Y so origin is top-left."""
    data = fbo.read(components=3, alignment=1)
    arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
    return arr[::-1].tobytes()


def record_animation(
    scene: CompiledScene,
    out_path: str | Path,
    *,
    duration: Optional[float] = None,
    fps: int = 30,
    width: int = 960,
    height: int = 540,
) -> Path:
    """Encode `duration` seconds of `scene` to ``out_path`` (MP4) at `fps`.

    Frames are rendered offscreen at the requested resolution and piped
    into ``ffmpeg`` as raw RGB. If ffmpeg is missing on PATH, raises
    ``FfmpegMissingError`` so the caller can pick a fallback.

    `duration` defaults to the scene's animate-block duration. For
    static scenes the caller must pass an explicit `duration`.
    """
    if shutil.which("ffmpeg") is None:
        raise FfmpegMissingError("ffmpeg is not installed or not on PATH")
    if duration is None:
        duration = scene.duration if scene.is_animated else 0.0
    if duration <= 0:
        raise ValueError(
            "record_animation: duration must be > 0 (pass --duration "
            "for static scenes or define an animate { duration = ... } block)"
        )
    if fps <= 0:
        raise ValueError("fps must be positive")

    n_frames = int(round(duration * fps))
    out = Path(out_path)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-an",
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-loglevel", "error",
        str(out),
    ]

    ctx, fbo = _build_offscreen(width, height)
    try:
        renderer = Renderer(ctx)
        renderer.upload(scene(0.0))
        camera = OrbitCamera()
        view = camera.view_matrix()
        proj = camera.projection_matrix(width / height)

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        assert proc.stdin is not None
        try:
            for i in range(n_frames):
                t = i / fps
                renderer.update(scene(t))
                renderer.draw(view, proj)
                proc.stdin.write(_read_rgb_flipped(fbo, width, height))
            proc.stdin.close()
        except BrokenPipeError as exc:
            proc.kill()
            raise RuntimeError("ffmpeg pipe closed unexpectedly") from exc
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg exited with status {ret}")
        return out
    finally:
        ctx.release()


def record_animation_pngs(
    scene: CompiledScene,
    out_dir: str | Path,
    *,
    duration: Optional[float] = None,
    fps: int = 30,
    width: int = 960,
    height: int = 540,
) -> Path:
    """Fallback for environments without ffmpeg: write frame_0000.png …
    into ``out_dir``. Returns the directory path.
    """
    if duration is None:
        duration = scene.duration if scene.is_animated else 0.0
    if duration <= 0:
        raise ValueError("record_animation_pngs: duration must be > 0")
    if fps <= 0:
        raise ValueError("fps must be positive")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    n_frames = int(round(duration * fps))

    ctx, fbo = _build_offscreen(width, height)
    try:
        renderer = Renderer(ctx)
        renderer.upload(scene(0.0))
        camera = OrbitCamera()
        view = camera.view_matrix()
        proj = camera.projection_matrix(width / height)
        for i in range(n_frames):
            t = i / fps
            renderer.update(scene(t))
            renderer.draw(view, proj)
            data = fbo.read(components=3, alignment=1)
            img = Image.frombytes("RGB", (width, height), data)
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            img.save(out / f"frame_{i:04d}.png", "PNG")
        return out
    finally:
        ctx.release()
