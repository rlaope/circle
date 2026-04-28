# circlelib

A tiny domain-specific language for declaring 3D scenes, with a built-in
desktop renderer.

You write a `.crl` file describing primitives (cubes, spheres, etc.) and
their positions, then run it: a black window opens and your scene is drawn.

```
$ circlelib run examples/hello.crl
```

## Why

`circlelib` is somewhere between a graphics library and a small programming
language. It has its own syntax, parser, AST, module/import system, and a
runtime that turns the AST into a 3D scene rendered with OpenGL.

The current release is intentionally small: static primitives only. The
codebase is structured so that animation can be added later without
rewriting the core.

## Quick example

```
import "modules/wheels" as wheels

component Car {
    body  = Cube(width=10, height=3, depth=5, position=(0, 1.5, 0))
    front = wheels.Pair(offset=(0, 0, 2))
    back  = wheels.Pair(offset=(0, 0, -2))
}

scene {
    Car(position=(0, 0, 0))
    Sphere(radius=2, position=(8, 2, 0), color=#ff5577)
}
```

## Built-in primitives (v0.1)

| Name       | Required keyword args                  | Optional                                   |
|------------|----------------------------------------|--------------------------------------------|
| `Cube`     | `width`, `height`, `depth`             | `position`, `color`, `rotation`            |
| `Sphere`   | `radius`                               | `position`, `color`                        |
| `Cylinder` | `radius`, `height`                     | `position`, `color`, `rotation`            |
| `Circle`   | `radius`                               | `tube` (default `radius * 0.1`), `position`, `color`, `rotation` |
| `Group`    | none — uses block body                 | `position`, `rotation`                     |

`Circle` is a true 3D ring (torus): `radius` is the distance from the
centre of the ring to the centre of the tube, and `tube` is the radius
of the tube. The window also draws a Matrix-style ground grid so you
can see depth even before any scene content is added.

All values use keyword arguments. Coordinates are tuples `(x, y, z)`.
Colors are hex literals like `#ff5577`.

## Modules

`import "relative/path" as alias` loads another `.crl` file relative to
the importing file. Components defined there can be referenced as
`alias.ComponentName(...)`. Circular imports raise an error.

## Install (from source)

```
pip install -e .[dev]
```

Then either:

```
circlelib run examples/hello.crl
# or
python -m circlelib run examples/hello.crl
```

## Project layout

```
circlelib/
├── grammar/circle.lark   # DSL grammar
├── parser/               # Lark tree -> AST
├── ast/                  # AST node definitions
├── runtime/              # Resolver, evaluator, primitive meshes
└── render/               # Window, camera, ModernGL renderer
```

## Tests

```
pytest
```

## Roadmap

- Animations (`animate { ... }` blocks)
- More primitives (Plane, Cone, Torus)
- Optional Three.js export for sharing scenes in the browser

## License

MIT
