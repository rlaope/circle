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


def _ffmpeg_available() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _gl_available(), reason="no standalone GL context")
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg missing")
def test_record_animation_writes_valid_mp4(tmp_path: Path):
    from circlelib.render.offscreen import record_animation
    from circlelib.runtime.evaluator import compile_program
    from circlelib.runtime.resolver import load

    src = tmp_path / "scene.crl"
    src.write_text(
        """
        scene {
            cube = Cube(width=1, height=1, depth=1, color=red)
        }
        animate {
            duration = 1
            cube.position = anim(t, (0, 0, 0), (4, 0, 0), 1)
        }
        """,
        encoding="utf-8",
    )
    out = tmp_path / "clip.mp4"
    record_animation(
        compile_program(load(src)), out,
        duration=0.5, fps=12, width=160, height=120,
    )
    assert out.exists() and out.stat().st_size > 0
    # MP4 (ISO BMFF) files start with `....ftyp`. Sniff the header.
    with open(out, "rb") as f:
        head = f.read(12)
    assert b"ftyp" in head, f"not an MP4: header={head!r}"


@pytest.mark.skipif(not _gl_available(), reason="no standalone GL context")
def test_record_pngs_fallback_writes_frame_files(tmp_path: Path):
    from circlelib.render.offscreen import record_animation_pngs
    from circlelib.runtime.evaluator import compile_program
    from circlelib.runtime.resolver import load

    src = tmp_path / "scene.crl"
    src.write_text(
        """
        scene { cube = Cube(width=1, height=1, depth=1) }
        animate {
            duration = 1
            cube.position = anim(t, (0, 0, 0), (1, 0, 0), 1)
        }
        """,
        encoding="utf-8",
    )
    out_dir = tmp_path / "frames"
    record_animation_pngs(
        compile_program(load(src)), out_dir,
        duration=0.5, fps=10, width=160, height=120,
    )
    files = sorted(out_dir.glob("frame_*.png"))
    assert len(files) == 5  # 0.5s * 10fps = 5 frames
    for f in files:
        assert f.stat().st_size > 0


def test_record_animation_raises_when_ffmpeg_missing(tmp_path: Path, monkeypatch):
    import shutil
    from circlelib.render.offscreen import (
        FfmpegMissingError,
        record_animation,
    )
    from circlelib.runtime.evaluator import compile_program
    from circlelib.runtime.resolver import load

    src = tmp_path / "scene.crl"
    src.write_text(
        """
        scene { cube = Cube(width=1, height=1, depth=1) }
        animate {
            duration = 1
            cube.position = anim(t, (0, 0, 0), (1, 0, 0), 1)
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(FfmpegMissingError):
        record_animation(
            compile_program(load(src)), tmp_path / "x.mp4",
            duration=0.1, fps=5, width=80, height=60,
        )
