"""Smoke test for offscreen PNG export.

Skipped automatically if a standalone GL context cannot be created
(e.g. headless CI without mesa/EGL drivers) or if Pillow is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _gl_available() -> bool:
    try:
        import moderngl
        ctx = moderngl.create_standalone_context()
        ctx.release()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _gl_available(), reason="no standalone GL context")
def test_export_png_writes_valid_image(tmp_path: Path):
    Image = pytest.importorskip("PIL.Image")

    from circlelib.render.offscreen import render_to_png
    from circlelib.runtime.evaluator import evaluate
    from circlelib.runtime.resolver import load

    src = tmp_path / "scene.crl"
    src.write_text(
        "scene { Cube(width=2, height=2, depth=2, color=red) }",
        encoding="utf-8",
    )
    out = tmp_path / "out.png"
    render_to_png(evaluate(load(src)), out, width=160, height=120)

    assert out.exists() and out.stat().st_size > 0
    with Image.open(out) as img:
        assert img.size == (160, 120)
        assert img.mode in ("RGB", "RGBA")
