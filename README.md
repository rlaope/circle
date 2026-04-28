# circlelib

> A tiny domain-specific language for declaring 3D scenes, with a built-in
> desktop renderer.

![circlelib hero — circles.crl rendered with the Matrix-style grid](docs/screenshots/circles-hero.png)

You write a `.crl` file describing primitives (cubes, spheres, 3D rings, …)
and their positions, then run it. A black window opens with a glowing
Matrix-style grid for orientation, your scene is rendered, and an orbit
camera lets you look around with the mouse.

```sh
$ circlelib run examples/circles.crl
```

---

## Why this exists

`circlelib` is somewhere between a graphics library and a small programming
language. It has its own syntax, parser, AST, module/import system, and a
runtime that turns the AST into a 3D scene rendered with OpenGL.

The current release (v0.1) is intentionally small: static primitives only.
The codebase is structured so that animation can be added later without
rewriting the core.

## At a glance

- **Custom DSL with its own grammar** — `.crl` files, parsed by
  [Lark](https://lark-parser.readthedocs.io/) into a typed AST.
- **Module system** — `import "modules/wheels" as wheels` resolves
  relative paths and detects circular imports.
- **Composable components** — define `component Car { ... }` once and
  instantiate it with arbitrary positions/rotations.
- **Five built-in primitives**, including a true 3D ring (torus).
- **OpenGL 3.3 renderer** with Lambert shading, an orbit camera, and a
  Matrix-style ground grid drawn behind the scene every frame.
- **CLI with a headless `--check` mode** for CI and unit testing.
- **15 pytest cases** covering the parser, resolver, and evaluator.

---

## A complete example

```crl
// examples/circles.crl

component Bullseye {
    Circle(radius=4.0, tube=0.10, position=(0, 0.05, 0), color=#ff3355)
    Circle(radius=3.2, tube=0.10, position=(0, 0.10, 0), color=#ffffff)
    Circle(radius=2.4, tube=0.10, position=(0, 0.15, 0), color=#ff3355)
    Circle(radius=1.6, tube=0.10, position=(0, 0.20, 0), color=#ffffff)
    Circle(radius=0.8, tube=0.10, position=(0, 0.25, 0), color=#ff3355)
}

component Tower {
    Circle(radius=2.0, tube=0.30, position=(0, 0.5, 0), color=#3aa0ff)
    Circle(radius=1.7, tube=0.28, position=(0, 1.5, 0), color=#4ab0ff)
    // ...stack of fat 3D rings
}

scene {
    Bullseye(position=(0, 0, 0))
    Tower(position=(-8, 0, -3))
    Tower(position=( 8, 0, -3))
    Circle(radius=5, tube=0.5, position=(0, 8, 0),
           rotation=(45, 0, 30), color=#ff66dd)
}
```

That single file produces the screenshot above.

---

## Built-in primitives

| Name       | Required keyword args                  | Optional                                                   |
|------------|----------------------------------------|------------------------------------------------------------|
| `Cube`     | `width`, `height`, `depth`             | `position`, `color`, `rotation`                            |
| `Sphere`   | `radius`                               | `position`, `color`                                        |
| `Cylinder` | `radius`, `height`                     | `position`, `color`, `rotation`                            |
| `Circle`   | `radius`                               | `tube` (default `radius * 0.1`), `position`, `color`, `rotation` |
| `Group`    | (none — uses block body)               | `position`, `rotation`                                     |

`Circle` is a true 3D torus: `radius` is the distance from the centre of
the ring to the centre of the tube, and `tube` is the radius of the tube
itself. Larger `tube` values produce chunky donut rings; smaller values
produce thin hoops.

### Argument value types

| Form           | Example       | Becomes               |
|----------------|---------------|-----------------------|
| Number         | `12.5`        | float                 |
| Tuple          | `(1, 2, 3)`   | 3-tuple of floats     |
| Hex color      | `#ff5577`     | `(r, g, b)` in `[0,1]`|
| String literal | `"label"`     | str                   |

---

## Modules and imports

```crl
// modules/wheels.crl
component Pair {
    Cylinder(radius=0.7, height=0.4,
             position=(-2, 0.7, 0), rotation=(0, 0, 90), color=#222222)
    Cylinder(radius=0.7, height=0.4,
             position=( 2, 0.7, 0), rotation=(0, 0, 90), color=#222222)
}
```

```crl
// hello.crl
import "modules/wheels" as wheels

component Car {
    body  = Cube(width=8, height=2, depth=4, position=(0, 1, 0), color=#3aa0ff)
    front = wheels.Pair(offset=(0, 0, 1.6))
    back  = wheels.Pair(offset=(0, 0, -1.6))
}

scene {
    Car(position=(0, 0, 0))
}
```

- Paths in `import` are relative to the importing file.
- The `.crl` extension is added automatically if you omit it.
- Circular imports raise `CircularImportError` at load time.

---

## How it works

`.crl` source flows through five stages before pixels appear:

```
   source.crl
       |
       v
+--------------+   Lark grammar (circle.lark)
|   Parser     |   tokens -> parse tree
+------+-------+
       |
       v
+--------------+   Transformer
|     AST      |   Module / Component / Scene / Call / GroupBlock / ...
+------+-------+
       |
       v
+--------------+   Resolver
|  Module      |   walks `import`s, builds alias tables,
|  Graph       |   detects circular imports
+------+-------+
       |
       v
+--------------+   Evaluator
|  SceneNode   |   inlines components, composes 4x4 transforms,
|     list     |   produces flat list of (mesh, transform, color)
+------+-------+
       |
       v
+--------------+   ModernGL
|   Renderer   |   single Lambert shader, orbit camera,
|  + GLFW loop |   Matrix-style grid, swap buffers
+--------------+
```

## Package structure

```
circlelib/
├── pyproject.toml
├── README.md
├── circlelib/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # `circlelib run scene.crl`
│   ├── grammar/
│   │   └── circle.lark         # DSL grammar
│   ├── parser/
│   │   └── transformer.py      # Lark tree -> AST
│   ├── ast/
│   │   └── nodes.py            # AST node dataclasses
│   ├── runtime/
│   │   ├── resolver.py         # import resolution + circular detection
│   │   ├── evaluator.py        # AST -> SceneNode list
│   │   └── primitives.py       # Mesh generators (cube/sphere/cylinder/torus)
│   └── render/
│       ├── window.py           # GLFW window + main loop + input
│       ├── renderer.py         # ModernGL pipeline + Matrix grid
│       └── camera.py           # Orbit camera
├── examples/
│   ├── hello.crl               # Car composed of imported wheel pairs
│   ├── circles.crl             # 3D-ring sculpture (the hero image)
│   └── modules/
│       └── wheels.crl
├── tests/
│   ├── test_parser.py          # 7 cases — grammar + AST
│   └── test_evaluator.py       # 8 cases — resolver + evaluator
└── docs/
    └── screenshots/
        └── circles-hero.png
```

---

## Install (from source)

```sh
git clone https://github.com/rlaope/circle.git
cd circle
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```sh
# Open a window with the hero scene:
circlelib run examples/circles.crl

# A simpler scene with imports:
circlelib run examples/hello.crl

# Headless: parse + evaluate only, no window required.
# Useful in CI or for syntax/runtime validation.
circlelib run examples/circles.crl --check
```

### Window controls

| Input                     | Action     |
|---------------------------|------------|
| Left mouse drag           | Orbit      |
| Scroll wheel              | Zoom       |
| ESC                       | Quit       |

## Tests

```sh
pytest
```

15 cases, ~0.1s wall time. They cover:

- empty source, scene/component parsing, color and string literals
- single-scene-per-file rule
- import statement + member access (`alias.Name`)
- group block transformation composition
- relative import resolution
- circular import detection
- unknown primitives and missing required arguments

---

## Roadmap

- [x] Custom grammar, parser, AST
- [x] Module system with relative imports + circular detection
- [x] Five built-in primitives (Cube, Sphere, Cylinder, Circle/torus, Group)
- [x] OpenGL renderer with orbit camera and Matrix-style grid
- [x] CLI + headless `--check`
- [ ] `animate { ... }` blocks (slot is reserved in the AST/evaluator design)
- [ ] More primitives: `Plane`, `Cone`, `Torus` with explicit args
- [ ] Optional Three.js export so scenes can be shared in the browser
- [ ] Shadows / textures / PBR materials

---

## License

MIT
