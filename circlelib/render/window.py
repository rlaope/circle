"""GLFW window + main loop.

`run_window(scene)` opens a window, uploads the scene to the GPU, and
runs an interactive orbit-camera loop until the window is closed.
For animated programs the loop calls the compiled-scene callable each
frame with the current time (looped over the scene's duration).
"""

from __future__ import annotations

from typing import List, Union

import glfw
import moderngl

from circlelib.render.camera import OrbitCamera
from circlelib.render.renderer import Renderer
from circlelib.runtime.evaluator import CompiledScene, SceneNode


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
) -> None:
    """Open a window and render `scene`.

    Accepts either a `CompiledScene` (with optional animation) or a
    plain list of `SceneNode` for backward compatibility. Animated
    scenes loop over their declared duration.
    """
    window = _init_glfw(title, width, height)
    ctx = moderngl.create_context()
    renderer = Renderer(ctx)

    if isinstance(scene, CompiledScene):
        compiled = scene
        animated = compiled.is_animated
        nodes = compiled(0.0)
    else:
        compiled = None
        animated = False
        nodes = scene
    renderer.upload(nodes)

    camera = OrbitCamera()
    start_time = glfw.get_time()

    state = {"dragging": False, "last_x": 0.0, "last_y": 0.0}

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

    glfw.set_mouse_button_callback(window, on_mouse_button)
    glfw.set_cursor_pos_callback(window, on_cursor)
    glfw.set_scroll_callback(window, on_scroll)
    glfw.set_key_callback(window, on_key)

    while not glfw.window_should_close(window):
        fb_w, fb_h = glfw.get_framebuffer_size(window)
        if fb_h == 0:
            glfw.poll_events()
            continue
        if animated and compiled is not None:
            elapsed = glfw.get_time() - start_time
            t = elapsed % compiled.duration if compiled.duration > 0 else 0.0
            renderer.update(compiled(t))
        ctx.viewport = (0, 0, fb_w, fb_h)
        view = camera.view_matrix()
        proj = camera.projection_matrix(fb_w / fb_h)
        renderer.draw(view, proj)
        glfw.swap_buffers(window)
        glfw.poll_events()

    glfw.terminate()
