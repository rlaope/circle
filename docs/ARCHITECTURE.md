# circlelib — Architecture

> For a market and strategic view: see [STRATEGY.md](STRATEGY.md).
> For the milestone task list: see [ROADMAP.md](ROADMAP.md).
> For user-facing `.crl` syntax/semantics: see [LANGUAGE.md](LANGUAGE.md).

This document explains how circlelib turns a `.crl` file into pixels and
where to extend it. Read it once before opening a non-trivial PR.

## Pipeline

```
   source.crl
       |
       v
+--------------+   Lark grammar (circlelib/grammar/circle.lark)
|   Parser     |   tokens -> parse tree
+------+-------+
       |
       v
+--------------+   Transformer (circlelib/parser/transformer.py)
|     AST      |   Module / Component / Scene / Call / GroupBlock / ...
+------+-------+
       |
       v
+--------------+   Resolver (circlelib/runtime/resolver.py)
|  Module      |   walks `import`s, builds alias tables,
|  Graph       |   detects circular imports
+------+-------+
       |
       v
+--------------+   Evaluator (circlelib/runtime/evaluator.py)
|  SceneNode   |   inlines components, composes 4x4 transforms,
|     list     |   produces flat list of (mesh, transform, color)
+------+-------+
       |
       v
+--------------+   Renderer (circlelib/render/*.py)
|   Renderer   |   single Lambert shader, orbit camera,
|  + GLFW loop |   Matrix-style grid, swap buffers
+--------------+
```

## Stages in detail

### 1. Grammar — `circlelib/grammar/circle.lark`
Lark grammar with Earley parser. Top-level rules: `import_stmt`,
`component_def`, `scene_def`. Statements are `assignment`, `call_stmt`,
or `group_stmt`. Argument values are number, string, hex color, tuple,
qualified name, or nested call.

**To extend:** add a rule, then add a Transformer method in step 2.

### 2. Transformer — `circlelib/parser/transformer.py`
`_ToAst` (Lark `Transformer`) turns the parse tree into the dataclasses
in `circlelib/ast/nodes.py`. Hex colors become `(r, g, b)` floats here.
Static checks (e.g. "only one scene block") run in `parse_source`.

**To extend:** new AST node → add a dataclass in `nodes.py` and a method
in `_ToAst`.

### 3. AST — `circlelib/ast/nodes.py`
Plain dataclasses. Frozen literals (`NumberLit`, `StringLit`,
`ColorLit`, `TupleLit`) and identifier nodes are hashable for cheap test
equality.

### 4. Resolver — `circlelib/runtime/resolver.py`
Loads `.crl` files relative to the importing file (auto-appends `.crl`
extension). Detects circular imports with an `in_progress` set. Returns
a `LoadedProgram(entry, modules: path→Module, alias_tables:
path→{alias→Module})`.

**Why per-path alias tables?** Each module sees only its own imports.
The evaluator carries `current_path` so `wheels.Pair` resolves to
whichever module is currently being evaluated.

### 5. Evaluator — `circlelib/runtime/evaluator.py`
Tree-walking interpreter. Walks the entry scene; for every call:
- Built-ins (`Cube`, `Sphere`, `Cylinder`, `Circle`, `Group`) → call
  `runtime.primitives` to make a mesh, wrap in a `SceneNode`.
- User components → inline-expand the body, accumulating the parent
  transform with the call's local transform.
- `alias.Name` calls → temporarily swap `current_path` to the imported
  module's path, then expand its component there.

`SceneNode` is the IR handed to the renderer: `(vertices, indices,
normals, transform, color)`.

### 6. Primitive meshes — `circlelib/runtime/primitives.py`
Each built-in returns numpy float32 `(verts, indices, normals)` in
object-local space. The cube uses per-face flat normals. The torus
(`Circle`) is parameterised by `(major_radius, tube_radius,
major_segments, minor_segments)`.

### 7. Renderer — `circlelib/render/{window,renderer,camera}.py`
- `window.py`: GLFW window, OpenGL 3.3 core context, input callbacks.
- `renderer.py`: ModernGL pipeline. Two shader programs — a Lambert
  shader for meshes and a flat shader for the Matrix grid.
- `camera.py`: orbit camera in spherical coordinates `(radius, yaw,
  pitch)`.

The grid lives in `_build_grid_buffer` and is rendered before the meshes
each frame.

## Where future features hook in

- **Animation (v0.3).** Add an `Animate` AST node. Split the evaluator
  into `static_pass` (today) and `frame_pass` (per-frame transform
  updates from time-keyed expressions). The renderer already loops; only
  the per-frame transform needs to be re-uploaded.
- **`--export-png` (v0.2).** Add an offscreen `moderngl.Framebuffer` in
  `render/` and a CLI subcommand that initialises the renderer without
  GLFW.
- **Three.js export (v0.4).** Walk the SceneNode list and emit glTF /
  Three.js JSON. No renderer changes needed.

## Testing strategy

- Parser tests in `tests/test_parser.py` use `parse_source` and assert
  AST equality.
- Evaluator tests in `tests/test_evaluator.py` use `tmp_path`, write
  `.crl` files, then call `load(...)` + `evaluate(...)` and assert on
  resulting `SceneNode` transforms.
- For new primitives, add at least one parser test and one evaluator
  test (transform composition is the easy thing to break).
- For renderer changes, prefer a smoke test that constructs a
  `moderngl.create_standalone_context()` if available; otherwise rely on
  `--check` integration in CI.

## Project conventions

- Code, comments, identifiers, commit messages, and GitHub issues are
  in **English**.
- Korean is fine in user-facing documentation snippets *only* when
  pulled from the strategy doc; everywhere else, English.
- Commits never include "Co-Authored-By", "Generated-with", or any
  AI-tooling traces.
- New AST nodes, primitives, or grammar rules ship with both example
  `.crl` and tests in the same PR.
