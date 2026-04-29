# circlelib — Language Reference

> The authoritative spec for the `.crl` syntax. The grammar lives in
> [`circlelib/grammar/circle.lark`](../circlelib/grammar/circle.lark);
> this document is the human-readable view of it. Examples mirror what
> the evaluator and renderer accept today.

For pipeline / extension internals see
[ARCHITECTURE.md](ARCHITECTURE.md). For tutorial-style intro see the
project [README](../README.md).

---

## 1. Source files

A `.crl` source file is UTF-8 text. The CLI takes a single entry file
and recursively loads anything it `import`s.

```
$ circlelib run examples/circles.crl
$ circlelib run examples/circles.crl --check     # parse + evaluate, no window
```

### Comments

```crl
// line comment, runs to end of line
/* block comment, may span lines */
```

### Whitespace

Whitespace, tabs, and newlines are insignificant; the grammar is
free-form.

---

## 2. Top-level structure

A program is a sequence of zero or more **top-level items**, in any
order:

| Item              | Form                              |
|-------------------|-----------------------------------|
| Import            | `import "path" as alias`          |
| Top-level binding | `name = expr`                     |
| Component         | `component Name { ... }`          |
| Scene             | `scene { ... }` (at most **one**) |

A file with no `scene` block is a **library file** — it can define
components and bindings that other files import, but it cannot be the
entry point for `circlelib run`.

A file with two or more `scene` blocks is a `SyntaxError`.

---

## 3. Lexical tokens

| Token       | Pattern                                    |
|-------------|--------------------------------------------|
| `NAME`      | `[A-Za-z_][A-Za-z0-9_]*`                   |
| `NUMBER`    | signed decimal — `42`, `-3.14`, `1e9`      |
| `STRING`    | double-quoted, `\"` and `\\` escapes       |
| `HEXCOLOR`  | `#` then exactly six hex digits — `#ff5577`|

Identifiers starting with an uppercase letter are conventionally
component names, primitives, or import aliases; lowercase names are
conventionally bindings and argument keys. The grammar does not enforce
the case convention.

---

## 4. Imports

```crl
import "modules/wheels" as wheels
import "shared/colors"  as palette
```

- Paths are **relative to the importing file**, never to the CWD.
- The `.crl` extension is appended automatically if you omit it.
- The alias (`wheels`, `palette`) is the only handle to the imported
  module; bare component names from another module are not visible.
- Circular imports raise `CircularImportError` at load time.
- Each module has its own top-level binding scope. Bindings do not leak
  across `import` boundaries.

Use the alias to reach a component:

```crl
scene {
    wheels.Pair(position=(0, 0, 0))
}
```

`alias.Name` is only valid in **call position**. You cannot pass
`palette.Red` as an argument value — values cross modules through
component arguments, not through identifiers.

---

## 5. Bindings

```crl
size = 5
gap  = size + 1
```

A binding evaluates `expr` once and binds the result to `name`.

### Scope

| Where the binding appears | Visible to                                     |
|---------------------------|------------------------------------------------|
| Module top level          | All bindings later in the file, all components in the file, the scene block |
| Inside a `component { }`  | All statements after it in the same component body |
| Inside a `scene { }`      | All statements after it in that scene block    |

Bindings are **strictly evaluated in source order** — a later binding
can reference an earlier one, but not vice versa.

```crl
component Stack {
    step = 1.5
    Cube(width=1, height=1, depth=1, position=(0, step * 0, 0))
    Cube(width=1, height=1, depth=1, position=(0, step * 1, 0))
}
```

### `name = call(...)` is NOT a binding

When the right-hand side is a primitive or component **call**, the
statement is a render statement; the name is just a label that is
currently ignored:

```crl
component Car {
    body = Cube(width=8, height=2, depth=4)   // renders the cube
    roof = Cube(width=4, height=1, depth=3)   // renders the cube
}
```

The leading `body =` and `roof =` document intent. They are not
referenceable. To bind a renderable component to a name and reuse it,
you would need first-class component values — that is **not** in the
language today.

---

## 6. Expressions

The expression grammar in precedence order, lowest to highest:

```
expr      ::=  add_expr
add_expr  ::=  mul_expr  (("+" | "-") mul_expr)*
mul_expr  ::=  unary     (("*" | "/" | "%") unary)*
unary     ::=  "-" unary | atom
atom      ::=  NUMBER | STRING | HEXCOLOR | tuple_lit
            | qualified_name | call | "(" expr ")"
tuple_lit ::=  "(" expr ("," expr)+ ","? ")"
```

### 6.1 Literals

| Form           | Example       | Type                    |
|----------------|---------------|-------------------------|
| Number         | `12.5`        | float                   |
| Tuple          | `(1, 2, 3)`   | tuple of values         |
| Hex color      | `#ff5577`     | `(r, g, b)` in `[0, 1]` |
| String literal | `"label"`     | str                     |

A tuple literal needs **at least one comma** (`(1, 2)`). A
parenthesised expression `(expr)` is just grouping, not a 1-tuple.

### 6.2 Identifiers

A bare identifier in an expression resolves through the active scopes
(innermost first):

1. The current component body's bindings.
2. The current module's top-level bindings.

If unresolved, `EvalError: undefined name: <name>`.

### 6.3 Arithmetic

The five binary operators `+ - * / %` and unary `-` are defined for:

- **Number, Number** → number
- **Tuple, Tuple** of equal length → component-wise
- Unary `-` on a tuple → negate each component

Mismatched-length tuples raise `EvalError`. Mixing scalar with tuple is
**not** supported (no broadcasting). Division or modulo by zero raises
`EvalError`.

```crl
position = (0, 0, 0) + (1, 2, 3)        // (1, 2, 3)
offset   = -(1, 0, 0)                   // (-1, 0, 0)
hop      = step * 2                     // scalar
```

### 6.4 Calls

```
call ::= qualified_name "(" arg_list? ")"
arg  ::= NAME "=" expr
```

All arguments are **keyword** arguments. There are no positional args.
Every primitive and every component is invoked the same way:

```crl
Cube(width=10, height=3, depth=5, position=(0, 1.5, 0))
wheels.Pair(position=(0, 0, 0))
```

Calls in **statement** position render. Calls in **expression** position
(as the value of an argument) are currently rejected — there are no
"value-returning components" yet.

---

## 7. Statements

A statement appears inside a `component { }` or `scene { }` body, or
inside a `Group { }` block.

| Statement       | Example                                            |
|-----------------|----------------------------------------------------|
| Bare call       | `Cube(width=1, height=1, depth=1)`                 |
| Named call      | `body = Cube(width=1, height=1, depth=1)`          |
| Value binding   | `step = size * 2`                                  |
| Group block     | `Group(position=(0, 1, 0)) { Sphere(radius=1) }`   |

### 7.1 Group blocks

`Group` is a built-in that does not render anything itself; it
multiplies its `position` / `rotation` into every child's transform.
Equivalent in spirit to a folder in a 3D editor.

```crl
Group(position=(10, 0, 0)) {
    Sphere(radius=1, position=(0, 5, 0))   // ends up at (10, 5, 0)
    Cube(width=1, height=1, depth=1)       // ends up at (10, 0, 0)
}
```

---

## 8. Built-in primitives

| Name       | Required keyword args      | Optional keyword args                                            |
|------------|----------------------------|------------------------------------------------------------------|
| `Cube`     | `width`, `height`, `depth` | `position`, `rotation`, `color`                                  |
| `Sphere`   | `radius`                   | `position`, `color`                                              |
| `Cylinder` | `radius`, `height`         | `position`, `rotation`, `color`                                  |
| `Circle`   | `radius`                   | `tube` (default `radius * 0.1`), `position`, `rotation`, `color` |
| `Plane`    | `width`, `depth`           | `position`, `rotation`, `color`                                  |
| `Group`    | (none — uses block body)   | `position`, `rotation`                                           |

Standard argument semantics:

- `position` — `(x, y, z)` translation in world units.
- `rotation` — `(rx, ry, rz)` in **degrees**, applied X then Y then Z.
- `color`    — hex literal `#rrggbb` (or any expression evaluating to a
  3-tuple of floats in `[0, 1]`).

`Circle` is a true 3D torus; `tube` is the radius of the tube around
the ring.

`Plane` is a flat XZ quad at `y=0` with normal `+Y`, sized `width`
along X and `depth` along Z. Use `rotation` to stand it up as a wall.

---

## 9. Components

```crl
component Car {
    // optional bindings (evaluated each time Car is instantiated)
    body_w = 8
    body_h = 2
    body_d = 4

    // statements: render calls, group blocks, more bindings...
    Cube(width=body_w, height=body_h, depth=body_d,
         position=(0, body_h / 2, 0), color=#3aa0ff)

    Sphere(radius=0.5, position=(0, body_h + 0.5, 0), color=#ffffff)
}
```

### Instantiation

`Car(position=(10, 0, 0), rotation=(0, 90, 0))` — the call's `position`
and `rotation` become the **parent transform** for everything in the
body. Other arguments are not yet plumbed into the body as parameters
(see §11 *Future*).

### Recursion

Direct or indirect recursion (`A` instantiates `B` which instantiates
`A`) raises `EvalError` at evaluation time.

---

## 10. Errors

Common categorical errors:

| Where     | Example trigger                              | Class                  |
|-----------|----------------------------------------------|------------------------|
| Parser    | Two `scene` blocks in one file               | `SyntaxError`          |
| Resolver  | `import "a"` cycles back to itself           | `CircularImportError`  |
| Resolver  | Path does not exist                          | `FileNotFoundError`    |
| Evaluator | Unknown primitive / component                | `EvalError`            |
| Evaluator | Missing required keyword arg                 | `EvalError`            |
| Evaluator | Identifier not bound in any visible scope    | `EvalError`            |
| Evaluator | `1 / 0`, `1 % 0`                             | `EvalError`            |
| Evaluator | Component recursion                          | `EvalError`            |

---

## 11. What the language does NOT have (yet)

Tracked in [ROADMAP.md](ROADMAP.md). The current language has, by
design, **no**:

- Functions or function definitions.
- Conditionals (`if`) or loops (`for` / `while`).
- String concatenation or string operators.
- Component parameters in expression positions (only `position` /
  `rotation` are inherited as the parent transform).
- First-class component values (you cannot pass `Cube` as an argument).
- Animation primitives — see ROADMAP v0.3.
- Module-level identifier export beyond the alias system.

Each of these is intentionally absent until a milestone justifies it.
