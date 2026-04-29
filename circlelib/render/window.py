"""GLFW window + main loop.

`run_window(scene)` opens a window, uploads the scene to the GPU, and
runs an interactive orbit-camera loop until the window is closed.
For animated programs the loop calls the compiled-scene callable each
frame with the current time (looped over the scene's duration).

When ``watch=True`` and an ``entry_path`` is supplied, the loop also
polls every loaded `.crl` for mtime changes and live-reloads the
scene when any file is saved. The orbit camera state is preserved
across reloads.
"""

from __future__ import annotations

import math
import sys
import time
from collections import deque
from pathlib import Path
from typing import List, Optional, Union

import glfw
import moderngl
import numpy as np
from PIL import Image

from circlelib.render.camera import OrbitCamera
from circlelib.render.hud import Hud
from circlelib.render.renderer import Renderer
from circlelib.runtime.evaluator import CompiledScene, SceneNode, compile_program
from circlelib.runtime.resolver import load
from circlelib.runtime.watcher import FileWatcher


def _snap_screen(ctx: moderngl.Context, fb_w: int, fb_h: int, scene_name: str) -> Path:
    """Read the default framebuffer into a PNG under ./screenshots/."""
    raw = ctx.screen.read(components=3, alignment=1)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape((fb_h, fb_w, 3))[::-1]
    img = Image.fromarray(arr, "RGB")
    out_dir = Path("screenshots")
    out_dir.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{scene_name}_{stamp}.png"
    img.save(path)
    return path


def _init_glfw(title: str, width: int, height: int):
    if not glfw.init():
        raise RuntimeError("failed to initialize GLFW")
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(width, height, title, None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("failed to create GLFW window")
    glfw.make_context_current(window)
    glfw.swap_interval(1)
    return window


def run_window(
    scene: Union[CompiledScene, List[SceneNode]],
    *,
    title: str = "circlelib",
    width: int = 960,
    height: int = 720,
    entry_path: Optional[Path] = None,
    watch: bool = False,
) -> None:
    """Open a window and render `scene`.

    Accepts either a `CompiledScene` (with optional animation) or a
    plain list of `SceneNode` for backward compatibility. Animated
    scenes loop over their declared duration.

    With ``watch=True`` and ``entry_path`` set, the loop polls every
    loaded `.crl` for mtime changes and live-reloads on save. Orbit
    camera state is preserved across reloads. Reload errors print one
    line to stderr and keep the previous good scene rendering.
    """
    window = _init_glfw(title, width, height)
    ctx = moderngl.create_context()
    renderer = Renderer(ctx)
    hud = Hud(ctx)

    if isinstance(scene, CompiledScene):
        compiled = scene
        animated = compiled.is_animated
        nodes = compiled(0.0)
    else:
        compiled = None
        animated = False
        nodes = scene
    renderer.upload(nodes)

    file_watcher: Optional[FileWatcher] = None
    if watch and entry_path is not None and compiled is not None:
        tracked = list(compiled.program.modules.keys())
        file_watcher = FileWatcher(tracked)
        print(f"watching {len(tracked)} module(s) for changes...", file=sys.stderr)

    camera = OrbitCamera()
    start_time = glfw.get_time()
    last_frame_time = start_time
    fps_window: deque[float] = deque(maxlen=60)

    state = {
        "dragging": False,
        "last_x": 0.0,
        "last_y": 0.0,
        "snap_requested": False,
    }

    def on_mouse_button(_w, button, action, _mods):
        if button == glfw.MOUSE_BUTTON_LEFT:
            state["dragging"] = action == glfw.PRESS
            state["last_x"], state["last_y"] = glfw.get_cursor_pos(window)

    def on_cursor(_w, x, y):
        if state["dragging"]:
            dx = x - state["last_x"]
            dy = y - state["last_y"]
            state["last_x"], state["last_y"] = x, y
            camera.rotate(dx, dy)

    def on_scroll(_w, _xoff, yoff):
        camera.zoom(yoff)

    def on_key(_w, key, _scan, action, _mods):
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_P and action == glfw.PRESS:
            state["snap_requested"] = True

    glfw.set_mouse_button_callback(window, on_mouse_button)
    glfw.set_cursor_pos_callback(window, on_cursor)
    glfw.set_scroll_callback(window, on_scroll)
    glfw.set_key_callback(window, on_key)

    while not glfw.window_should_close(window):
        fb_w, fb_h = glfw.get_framebuffer_size(window)
        if fb_h == 0:
            glfw.poll_events()
            continue

        now = glfw.get_time()
        dt = now - last_frame_time
        last_frame_time = now
        if dt > 0:
            fps_window.append(1.0 / dt)

        if file_watcher is not None and entry_path is not None and file_watcher.changed():
            try:
                program = load(entry_path)
                new_compiled = compile_program(program)
                compiled = new_compiled
                animated = compiled.is_animated
                start_time = now
                renderer.upload(compiled(0.0))
                file_watcher.retarget(list(program.modules.keys()))
                hud.clear_error()
                print(
                    f"reloaded {entry_path} ({len(program.modules)} module(s))",
                    file=sys.stderr,
                )
            except Exception as e:
                # Keep the previous good scene running; surface the
                # error both on stderr and inside the HUD so the user
                # sees it without needing the terminal in view.
                err_msg = f"{e.__class__.__name__}: {e}"
                hud.set_error(err_msg)
                print(f"reload failed: {err_msg}", file=sys.stderr)

        t = 0.0
        if animated and compiled is not None:
            elapsed = now - start_time
            t = elapsed % compiled.duration if compiled.duration > 0 else 0.0
            renderer.update(compiled(t))

        ctx.viewport = (0, 0, fb_w, fb_h)
        view = camera.view_matrix()
        proj = camera.projection_matrix(fb_w / fb_h)
        renderer.draw(view, proj)

        eye = camera.eye()
        fps = sum(fps_window) / len(fps_window) if fps_window else 0.0
        if compiled is not None and compiled.is_animated:
            t_line = f"t      {t:5.2f} / {compiled.duration:5.2f}"
        else:
            t_line = "t      static"
        hud.set_text(
            "camera\n"
            f"yaw    {math.degrees(camera.yaw):6.1f}\n"
            f"pitch  {math.degrees(camera.pitch):6.1f}\n"
            f"radius {camera.radius:6.2f}\n"
            f"eye    ({eye[0]:5.1f},{eye[1]:5.1f},{eye[2]:5.1f})\n"
            f"{t_line}\n"
            f"fps    {fps:6.1f}"
        )
        hud.draw(fb_w, fb_h)

        if state["snap_requested"]:
            state["snap_requested"] = False
            scene_name = entry_path.stem if entry_path is not None else "scene"
            try:
                path = _snap_screen(ctx, fb_w, fb_h, scene_name)
                print(f"snapped {path}", file=sys.stderr)
            except Exception as e:
                print(f"snap failed: {e}", file=sys.stderr)

        glfw.swap_buffers(window)
        glfw.poll_events()

    glfw.terminate()
