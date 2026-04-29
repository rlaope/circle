"""Command-line entry point for circlelib.

    circlelib run path/to/scene.crl

Loads the program, evaluates it into a list of SceneNodes, and opens a
window to render the result. `--check` runs only the parser/evaluator,
which is useful in headless environments and CI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from circlelib import __version__
from circlelib.runtime.evaluator import evaluate
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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        program = load(args.file)
        nodes = evaluate(program)
        print(f"loaded {len(program.modules)} module(s), {len(nodes)} node(s)")
        if args.check:
            return 0
        if args.export_png is not None:
            # Imported lazily so `--check` works without GPU access.
            from circlelib.render.offscreen import render_to_png

            out = render_to_png(
                nodes, args.export_png, width=args.width, height=args.height
            )
            print(f"wrote {out}")
            return 0
        # Imported lazily so `--check` works without a display / GPU.
        from circlelib.render.window import run_window

        run_window(nodes, width=args.width, height=args.height)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
