# Changelog

All notable changes to circlelib are documented here. The format is
loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/)
once it reaches 1.0.0.

## [Unreleased]

- Project metadata polish for v1.0 prep: PyPI classifiers, keywords,
  project URLs, this CHANGELOG, a stability policy doc
  (`docs/STABILITY.md`), and `circlelib new` scaffolder.
- **Bug fix (behaviour change)**: `python -m circlelib` previously
  swallowed the CLI's return code and always exited 0. It now calls
  `sys.exit(main())` so non-zero exits from `run`/`record`/`export`/
  `install`/`new` propagate to the shell. Scripts that depended on
  the old always-zero behaviour (e.g. `circlelib run bad.crl &&
  echo ok` printing "ok") will now see the correct exit code.
- `circlelib new --template` validates against `argparse.choices`
  (auto-derived from the shipped template list) so the help output
  stays in sync as templates are added.

## [0.6.0] — 2026-04-29

- **Standard library** under `circlelib/stdlib/` shipped with the
  package: furniture (Chair, Stool, Table, Desk, Lamp), vehicles
  (Car, Truck, Pair, Quad), structures (Tower, Column, Arch), and
  geometry helpers (Axes, Crosshair). Imported with the `@stdlib/...`
  prefix.
- **Third-party packages**: `circlelib install <owner>/<repo>` clones
  from GitHub (or `--from <dir>` for a local install) into
  `~/.circlelib/packages/<owner>/<repo>/`. The same `@<owner>/<repo>/`
  prefix used for stdlib resolves into that cache. `--list`,
  `--upgrade`, and `CIRCLELIB_HOME` env-var override included.
- Three composed example scenes under `examples/stdlib/` walked
  through with renders in `docs/stdlib_gallery.md`.

## [0.5.0] — 2026-04-29

- **Live coding** with `circlelib run --watch`: every save of the
  entry file or any imported module re-parses, recompiles, and swaps
  the scene without closing the window. Orbit-camera state (yaw,
  pitch, radius) is preserved across reloads.
- Failed reloads display a wrapped red error band inside the HUD
  (with a 3-line cap and ellipsis truncation) until the next
  successful save. Errors continue to print to stderr in parallel.
- `P` key snapshots the current frame to
  `screenshots/<scene>_<YYYYMMDD_HHMMSS>.png`. The snapshot is taken
  after the HUD draws and before swap_buffers, so it matches what the
  user sees on screen.

## [0.4.0] — 2026-04-29

- **glTF / Three.js exporter**: `circlelib export scene.crl
  --target=threejs --out=site/` writes a static-frame `scene.gltf`
  plus an interactive Three.js viewer (importmap + GLTFLoader +
  OrbitControls). `--embed` inlines the binary buffer as base64.

## [0.3.0] — 2026-04-29

- **Animation as first-class citizens**: `animate { duration = N;
  label.attr = anim(t, start, end, duration[, easing=NAME]) }` block.
- Easings: `linear` (default), `ease_in`, `ease_out`, `ease_in_out`,
  `bounce`.
- `circlelib record scene.crl --out clip.mp4` pipes offscreen frames
  into ffmpeg; `--png-fallback` writes a PNG sequence when ffmpeg is
  not on PATH.
- `docs/gallery.md` walks through six animated demos under
  `examples/anim/` with screenshots.
- HUD overlay in the run window shows orbit-camera state, animation
  time, and FPS.

## [0.2.0] — 2026-04-29

- Top-level bindings + arithmetic expressions in argument values.
- `Plane` and `Cone` primitives.
- Extra color formats: `rgb(r, g, b)`, `rgba(r, g, b, a)`, named
  CSS colors, `#rgb` shorthand.
- `circlelib run scene.crl --export-png file.png` headless render.
- GitHub Actions CI (pytest + render every example) with PR preview
  PNGs.
- VSCode extension scaffold under `tools/vscode-circlelib/` (syntax
  highlighting + snippets).

## [0.1.0] — 2026-04-29

- Initial public release.
- Lark grammar, AST, resolver with circular-import detection,
  evaluator that composes 4×4 transforms, ModernGL renderer with a
  Lambert shader and orbit camera.
- Built-in primitives: `Cube`, `Sphere`, `Cylinder`, `Circle` (true
  3D torus), `Group`.
- Module imports relative to the importing file via
  `import "path" as alias`.
