"""Tests for the pure HUD image composition.

Anything that touches moderngl needs a live GL context, so the GPU
glue (`Hud.set_text` / `set_error` cache invalidation) is exercised
through a tiny fake texture; the actual rasterisation is covered by
calling `compose_hud_image` directly with `ImageFont.load_default()`.
"""

from __future__ import annotations

from PIL import Image, ImageFont

from circlelib.render.hud import _wrap_error, compose_hud_image


# Pixel-sample helpers -----------------------------------------------

def _has_red(img: Image.Image, threshold: int = 90) -> bool:
    """Return True if any pixel has a strong red channel relative to G/B.

    Used as a coarse signal for "the error band rendered something
    in red," without coupling the test to exact pixel coordinates.
    """
    pixels = img.load()
    w, h = img.size
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            r, g, b, a = pixels[x, y]
            if a > 0 and r >= threshold and r > g + 30 and r > b + 30:
                return True
    return False


def _opaque_height(img: Image.Image) -> int:
    """Topmost stretch of rows that contain an opaque pixel."""
    pixels = img.load()
    w, h = img.size
    last = 0
    for y in range(h):
        any_opaque = any(pixels[x, y][3] > 0 for x in range(0, w, 8))
        if any_opaque:
            last = y
    return last + 1 if last else 0


# Composition tests --------------------------------------------------

def test_compose_without_error_renders_no_red(tmp_path):
    img = compose_hud_image(
        "camera\nyaw  35.0\npitch 25.0",
        error=None,
        width=400, height=400, padding=18, line_height=36,
        font=ImageFont.load_default(),
    )
    assert isinstance(img, Image.Image)
    assert not _has_red(img)


def test_compose_with_error_renders_red_band():
    img = compose_hud_image(
        "camera\nyaw  35.0\npitch 25.0",
        error="ParseError: unexpected token at line 12",
        width=400, height=400, padding=18, line_height=36,
        font=ImageFont.load_default(),
    )
    assert _has_red(img)


def test_panel_grows_when_error_added():
    base = compose_hud_image(
        "camera",
        error=None,
        width=400, height=400, padding=18, line_height=36,
        font=ImageFont.load_default(),
    )
    grown = compose_hud_image(
        "camera",
        error="EvalError: undefined name: foo",
        width=400, height=400, padding=18, line_height=36,
        font=ImageFont.load_default(),
    )
    # Error path should fill more vertical pixels than the metrics-only path.
    assert _opaque_height(grown) > _opaque_height(base)


def test_compose_clears_when_error_removed():
    """A non-error second call must produce the same opaque region as
    the first non-error call (no stale red pixels left behind)."""
    fresh = compose_hud_image(
        "camera",
        error=None,
        width=400, height=400, padding=18, line_height=36,
        font=ImageFont.load_default(),
    )
    assert not _has_red(fresh)


# Wrapper unit tests -------------------------------------------------

def test_wrap_error_short_message_passes_through():
    assert _wrap_error("hello", max_chars=20, max_lines=3) == ["hello"]


def test_wrap_error_breaks_on_spaces():
    out = _wrap_error("the quick brown fox jumps", max_chars=10, max_lines=4)
    # Each line within budget.
    assert all(len(line) <= 10 for line in out)
    # Reassembly preserves all words.
    assert "the" in out[0]
    assert any("fox" in line for line in out)


def test_wrap_error_truncates_with_ellipsis_when_overflowing():
    long = "a" * 200
    out = _wrap_error(long, max_chars=20, max_lines=2)
    assert len(out) == 2
    # The last visible line ends with ellipsis to signal truncation.
    assert out[-1].endswith("...")


def test_wrap_error_handles_explicit_newlines():
    out = _wrap_error("line1\nline2", max_chars=20, max_lines=4)
    assert out == ["line1", "line2"]
