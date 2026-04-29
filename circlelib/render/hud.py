"""Top-right HUD overlay rendered as a screen-space textured quad.

Shows the orbit camera's `yaw`, `pitch`, `radius`, and `eye` plus the
animation `t / duration` and a smoothed FPS reading. Text is rasterised
with Pillow into a small RGBA texture; the texture is reuploaded only
when the rendered text actually changes.

When ``set_error(msg)`` is called the panel grows a red error band at
the bottom showing the latest reload failure. ``clear_error()`` removes
it. The image-composition logic is a pure top-level function so unit
tests can exercise it without a GL context.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont


_HUD_VS = """
#version 330
in vec2 in_position;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    v_uv = in_uv;
}
"""

_HUD_FS = """
#version 330
uniform sampler2D u_tex;
in vec2 v_uv;
out vec4 frag;
void main() {
    frag = texture(u_tex, v_uv);
}
"""

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/Library/Fonts/Andale Mono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
]


def _load_mono_font(size: int = 28):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_error(text: str, max_chars: int, max_lines: int) -> List[str]:
    """Greedy character-wrap of an error message into a fixed line budget.

    Splits on existing newlines first, then breaks any over-length line
    on the nearest preceding space (or hard-cuts when no space exists).
    The last line is truncated with an ellipsis when the message overflows.
    """
    out: List[str] = []
    for raw_line in text.splitlines() or [""]:
        remaining = raw_line
        while remaining:
            if len(remaining) <= max_chars:
                out.append(remaining)
                remaining = ""
                break
            cut = remaining.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            out.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
            if len(out) == max_lines:
                break
        if len(out) >= max_lines:
            break
    if len(out) > max_lines:
        out = out[:max_lines]
    if out and len(text) > sum(len(s) for s in out) + len(out) - 1:
        # Trailing ellipsis if anything was truncated.
        last = out[-1]
        if len(last) >= 3:
            out[-1] = last[: max(0, max_chars - 3)] + "..."
    return out


def compose_hud_image(
    text: str,
    error: Optional[str],
    *,
    width: int,
    height: int,
    padding: int,
    line_height: int,
    font,
    error_line_height: int = 28,
    error_max_lines: int = 3,
) -> Image.Image:
    """Pure rasteriser used both by ``Hud.set_text`` and unit tests.

    Returns an RGBA image where unused vertical space is fully
    transparent — the panel visually shrinks/grows with the content.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    lines = text.splitlines()
    metrics_h = padding + len(lines) * line_height + padding

    # Wrap the error to fit (rough char budget based on panel width).
    err_lines: List[str] = []
    err_block_h = 0
    if error:
        max_chars = max(20, (width - 2 * padding) // 12)
        err_lines = _wrap_error(error, max_chars=max_chars, max_lines=error_max_lines)
        err_block_h = padding // 2 + (1 + len(err_lines)) * error_line_height + padding

    total_h = min(height, metrics_h + err_block_h)

    # Panel background only covers content height.
    draw.rectangle(((0, 0), (width, total_h)), fill=(0, 0, 0, 180))

    # Metrics text.
    y = padding
    for i, line in enumerate(lines):
        color = (0, 255, 200, 255) if i == 0 else (220, 235, 255, 255)
        draw.text((padding, y), line, fill=color, font=font)
        y += line_height

    # Error band (red header + wrapped lines).
    if err_lines:
        # Thin separator line.
        sep_y = y + padding // 2
        draw.line([(padding, sep_y), (width - padding, sep_y)], fill=(120, 30, 30, 220), width=2)
        y = sep_y + padding // 2
        draw.text((padding, y), "ERROR", fill=(255, 90, 90, 255), font=font)
        y += error_line_height
        for line in err_lines:
            draw.text((padding, y), line, fill=(255, 200, 200, 255), font=font)
            y += error_line_height

    return img


class Hud:
    WIDTH_PX = 580
    HEIGHT_PX = 480  # tall enough to fit the metrics + a 3-line error band
    MARGIN_PX = 20
    LINE_HEIGHT_PX = 36
    PADDING_PX = 18

    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        self._program = ctx.program(vertex_shader=_HUD_VS, fragment_shader=_HUD_FS)
        self._font = _load_mono_font(28)

        self._texture = ctx.texture((self.WIDTH_PX, self.HEIGHT_PX), 4)
        self._texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._cached_key: Optional[Tuple[str, Optional[str]]] = None
        self._error: Optional[str] = None
        # Pre-fill with a fully transparent panel so the first frame
        # doesn't flash a black box.
        blank = Image.new(
            "RGBA", (self.WIDTH_PX, self.HEIGHT_PX), (0, 0, 0, 0)
        )
        self._texture.write(blank.transpose(Image.FLIP_TOP_BOTTOM).tobytes())

        # Quad VBO/IBO (positions written every frame because they
        # depend on viewport size). 4 verts × 4 floats × 4 bytes.
        self._vbo = ctx.buffer(reserve=4 * 4 * 4)
        ibo_data = np.array([0, 1, 2, 0, 2, 3], dtype="u4").tobytes()
        self._ibo = ctx.buffer(ibo_data)
        self._vao = ctx.vertex_array(
            self._program,
            [(self._vbo, "2f 2f", "in_position", "in_uv")],
            self._ibo,
        )

    def set_text(self, text: str) -> None:
        key = (text, self._error)
        if key == self._cached_key:
            return
        self._cached_key = key
        img = compose_hud_image(
            text,
            self._error,
            width=self.WIDTH_PX,
            height=self.HEIGHT_PX,
            padding=self.PADDING_PX,
            line_height=self.LINE_HEIGHT_PX,
            font=self._font,
        )
        flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
        self._texture.write(flipped.tobytes())

    def set_error(self, message: str) -> None:
        """Sticky red error band; cleared by `clear_error()` or by
        receiving a fresh successful reload."""
        if message == self._error:
            return
        self._error = message
        # Force the next `set_text` call to re-rasterise even if its
        # text content is unchanged.
        self._cached_key = None

    def clear_error(self) -> None:
        if self._error is None:
            return
        self._error = None
        self._cached_key = None

    def draw(self, fb_w: int, fb_h: int) -> None:
        if fb_w <= 0 or fb_h <= 0:
            return
        m = self.MARGIN_PX
        w = self.WIDTH_PX
        h = self.HEIGHT_PX
        # NDC coords for the panel pinned to the upper-right corner.
        x_right = 1.0 - (m * 2.0 / fb_w)
        x_left = x_right - (w * 2.0 / fb_w)
        y_top = 1.0 - (m * 2.0 / fb_h)
        y_bot = y_top - (h * 2.0 / fb_h)
        verts = np.array(
            [
                [x_left, y_top, 0.0, 1.0],   # tl
                [x_left, y_bot, 0.0, 0.0],   # bl
                [x_right, y_bot, 1.0, 0.0],  # br
                [x_right, y_top, 1.0, 1.0],  # tr
            ],
            dtype="f4",
        )
        self._vbo.write(verts.tobytes())
        self._texture.use(location=0)
        self._program["u_tex"].value = 0
        # HUD draws on top of the scene without writing the depth buffer.
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (
            moderngl.SRC_ALPHA,
            moderngl.ONE_MINUS_SRC_ALPHA,
        )
        self._vao.render(mode=moderngl.TRIANGLES, vertices=6)
        self.ctx.disable(moderngl.BLEND)
        self.ctx.enable(moderngl.DEPTH_TEST)
