"""Top-right HUD overlay rendered as a screen-space textured quad.

Shows the orbit camera's `yaw`, `pitch`, `radius`, and `eye` plus the
animation `t / duration` and a smoothed FPS reading. Text is rasterised
with Pillow into a small RGBA texture; the texture is reuploaded only
when the rendered text actually changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

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


class Hud:
    WIDTH_PX = 580
    HEIGHT_PX = 310
    MARGIN_PX = 20
    LINE_HEIGHT_PX = 36
    PADDING_PX = 18

    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        self._program = ctx.program(vertex_shader=_HUD_VS, fragment_shader=_HUD_FS)
        self._font = _load_mono_font(28)

        self._texture = ctx.texture((self.WIDTH_PX, self.HEIGHT_PX), 4)
        self._texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._cached_text: Optional[str] = None
        # Pre-fill with blank panel so the first frame doesn't flash.
        blank = Image.new(
            "RGBA", (self.WIDTH_PX, self.HEIGHT_PX), (0, 0, 0, 160)
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
        if text == self._cached_text:
            return
        self._cached_text = text
        img = Image.new(
            "RGBA", (self.WIDTH_PX, self.HEIGHT_PX), (0, 0, 0, 180)
        )
        draw = ImageDraw.Draw(img)
        # Header row in green; body rows lighter.
        lines = text.splitlines()
        y = self.PADDING_PX
        for i, line in enumerate(lines):
            color = (0, 255, 200, 255) if i == 0 else (220, 235, 255, 255)
            draw.text((self.PADDING_PX, y), line, fill=color, font=self._font)
            y += self.LINE_HEIGHT_PX
        flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
        self._texture.write(flipped.tobytes())

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
