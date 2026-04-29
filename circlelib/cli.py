"""Command-line entry point for circlelib.

Two subcommands:

  circlelib run path/to/scene.crl
      Loads the program, compiles it into a frame callable, and either
      opens a window, exports a single PNG (`--export-png`), or just
      parses + evaluates (`--check`).

  circlelib record path/to/scene.crl --out clip.mp4
      Encodes an animated scene to MP4 by piping offscreen frames into
      ffmpeg. Falls back to a PNG sequence with `--png-fallback` when
      ffmpeg is missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from circlelib import __version__
from circlelib.runtime.evaluator import compile_program
from circlelib.runtime.resolver import load


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="circlelib")
    parser.add_argument(
        "--version", action="version", version=f"circlelib {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="render a .crl file in a window")
    run.add_argument("file", type=Path, help="path to a .crl file")
    run.add_argument(
        "--check",
        action="store_true",
        help="parse + evaluate only, do not open a window",
    )
    run.add_argument(
        "--export-png",
        type=Path,
        default=None,
        metavar="PATH",
        help="render headlessly to a PNG file instead of opening a window",
    )
    run.add_argument("--width", type=int, default=960)
    run.add_argument("--height", type=int, default=720)

    record = sub.add_parser(
        "record", help="render an animated .crl to MP4 (or a PNG sequence)"
    )
    record.add_argument("file", type=Path, help="path to a .crl file")
    record.add_argument(
        "--out", type=Path, required=True,
        help="output MP4 path (or directory for --png-fallback)",
    )
    record.add_argument(
        "--duration", type=float, default=None,
        help="seconds (defaults to the scene's animate { duration })",
    )
    record.add_argument("--fps", type=int, default=30)
    record.add_argument("--width", type=int, default=960)
    record.add_argument("--height", type=int, default=540)
    record.add_argument(
        "--png-fallback", action="store_true",
        help="write a frame_0000.png sequence instead of an MP4 "
             "(useful when ffmpeg is unavailable)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        program = load(args.file)
        scene = compile_program(program)
        # Initial node list at t=0 just for a quick "loaded N node(s)"
        # diagnostic; the window/PNG paths will (re-)evaluate frames.
        initial = scene(0.0)
        if scene.is_animated:
            print(
                f"loaded {len(program.modules)} module(s), "
                f"{len(initial)} node(s) (animate duration={scene.duration}s)"
            )
        else:
            print(f"loaded {len(program.modules)} module(s), {len(initial)} node(s)")
        if args.check:
            return 0
        if args.export_png is not None:
            # Imported lazily so `--check` works without GPU access.
            from circlelib.render.offscreen import render_to_png

            out = render_to_png(
                initial, args.export_png, width=args.width, height=args.height
            )
            print(f"wrote {out}")
            return 0
        # Imported lazily so `--check` works without a display / GPU.
        from circlelib.render.window import run_window

        run_window(scene, width=args.width, height=args.height)
        return 0

    if args.command == "record":
        program = load(args.file)
        scene = compile_program(program)
        if not scene.is_animated and args.duration is None:
            print(
                "error: scene has no `animate { duration = ... }` block; "
                "pass --duration to record a still frame range.",
                file=sys.stderr,
            )
            return 2
        from circlelib.render.offscreen import (
            FfmpegMissingError,
            record_animation,
            record_animation_pngs,
        )
        if args.png_fallback:
            out = record_animation_pngs(
                scene, args.out,
                duration=args.duration, fps=args.fps,
                width=args.width, height=args.height,
            )
            print(f"wrote PNG sequence to {out}/")
            return 0
        try:
            out = record_animation(
                scene, args.out,
                duration=args.duration, fps=args.fps,
                width=args.width, height=args.height,
            )
        except FfmpegMissingError:
            print(
                "error: ffmpeg not found on PATH. Install ffmpeg "
                "(e.g. `brew install ffmpeg`) or rerun with "
                "--png-fallback to dump a PNG sequence instead.",
                file=sys.stderr,
            )
            return 3
        print(f"wrote {out}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
