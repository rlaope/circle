# Stability policy

> What is allowed to change between releases, and what is not. This
> document is the single source of truth for backwards-compatibility
> commitments. Read it before proposing breaking changes.

## Status: pre-1.0

circlelib is currently at **0.6.0**. Until 1.0.0 is tagged, the
project follows a relaxed policy: minor versions may change anything,
including grammar and CLI surface. We try to avoid breakage on a best-
effort basis, but we do not guarantee it pre-1.0.

The 1.0.0 release will freeze the surfaces below. Anything not listed
here is explicitly **not** part of the stable API.

## What 1.0 will guarantee

### `.crl` source compatibility

A `.crl` file that parses and runs on a given 1.x release will continue
to parse and run on every later 1.x release. Specifically, the following
constructs will keep their current syntax and semantics:

- Top-level: `import "..." as <alias>`, `name = expr`, `component
  Name { ... }`, and `scene { ... }`.
- Animate block: `animate { duration = <expr>; label.attr = <expr> }`
  with `t` in scope and the `anim()` builtin.
- All built-in primitives currently documented in
  [LANGUAGE.md](LANGUAGE.md) §8: `Cube`, `Sphere`, `Cylinder`,
  `Circle`, `Plane`, `Cone`, and `Group` — including their required
  / optional keyword arguments.
- Color formats: hex literals, named CSS colors, `rgb()`, `rgba()`,
  `#rgb` shorthand.
- Arithmetic, tuples, identifier scoping rules from §5–§6.
- Module resolution: relative paths, `@stdlib/...`, and
  `@<owner>/<repo>/...`.
- Easing names: `linear`, `ease_in`, `ease_out`, `ease_in_out`,
  `bounce`.

### CLI surface

Running `circlelib --help` on a 1.x release lists at minimum these
subcommands with the documented flags:

- `circlelib run <file> [--check] [--export-png PATH] [--width W]
  [--height H] [--watch]`
- `circlelib record <file> --out PATH [--duration N] [--fps N]
  [--width W] [--height H] [--png-fallback]`
- `circlelib export <file> --target threejs --out DIR [--embed]
  [--time T]`
- `circlelib install <slug> [--from DIR] [--upgrade] [--list]`

Future minor releases may add new subcommands and new optional flags,
but they cannot remove or rename the surface above.

### Python API

The following imports remain stable across 1.x:

- `from circlelib.runtime.resolver import load`
- `from circlelib.runtime.evaluator import compile_program, evaluate,
  CompiledScene, SceneNode`
- `from circlelib.runtime.installer import install_from_local,
  install_from_github, list_installed`
- `circlelib.__version__`

Internal modules (`circlelib.parser._*`, `circlelib.render.*`,
private helpers prefixed with `_`) are **not** part of the stable API
and may change in any release.

### Standard library catalog

Components currently shipped in `circlelib/stdlib/` keep their names,
import paths, and the **shape of the rendered output** across 1.x.
Their colours and exact mesh tessellation are not stable — a future
release may sharpen a chair's legs without it counting as a break.

## What 1.0 will NOT guarantee

- The exact tessellation count of any primitive (e.g. number of
  segments in `Cylinder`).
- The exact framebuffer pixel output of any scene at the byte level
  (we run snapshot tests on shape / leaf counts, not pixel diffs).
- The Three.js viewer template's HTML structure (`docs/STABILITY.md`
  treats it as bundled artwork, not a stable contract).
- Internal AST class layouts, evaluator helpers, or renderer internals.
- HUD layout, fonts, or hot-key bindings beyond the four documented
  ones (left-drag / scroll / `P` / `ESC`).

## Deprecation policy

If we ever need to remove or rename a stable surface inside 1.x:

1. The change is announced in the CHANGELOG one minor release ahead.
2. A deprecation warning fires at runtime for at least one full minor
   release before removal.
3. The removal itself bumps the major version.

## Why this exists

The roadmap explicitly targets people who would otherwise reach for
OpenSCAD, manim, or hand-rolled Three.js. Those audiences need to know
that a `.crl` file written today will still work next year. This
document is the contract that makes "write a `.crl`, ship the file"
viable as a workflow.
