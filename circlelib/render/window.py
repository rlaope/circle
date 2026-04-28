"""GLFW window + main loop.

`run_window(nodes)` opens a window, uploads the scene to the GPU, and
runs an interactive orbit-camera loop until the window is closed.
"""

from __future__ import annotations

from typing import List

import glfw
import moderngl

from circlelib.render.camera import OrbitCamera
from circlelib.render.renderer import Renderer
from circlelib.runtime.evaluator import SceneNode


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
    nodes: List[SceneNode],
    *,
    title: str = "circlelib",
    width: int = 960,
    height: int = 720,
) -> None:
    window = _init_glfw(title, width, height)
    ctx = moderngl.create_context()
    renderer = Renderer(ctx)
    renderer.upload(nodes)
    camera = OrbitCamera()

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
        ctx.viewport = (0, 0, fb_w, fb_h)
        view = camera.view_matrix()
        proj = camera.projection_matrix(fb_w / fb_h)
        renderer.draw(view, proj)
        glfw.swap_buffers(window)
        glfw.poll_events()

    glfw.terminate()
