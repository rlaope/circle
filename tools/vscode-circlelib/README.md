# vscode-circlelib

Syntax highlighting and snippets for `.crl` files in VSCode.

## Install (development)

1. Open VSCode.
2. Run **Developer: Install Extension from Location…** from the
   Command Palette (`Cmd/Ctrl + Shift + P`).
3. Pick this folder (`tools/vscode-circlelib/`).
4. Open any `.crl` file under `examples/` — keywords, primitives,
   numbers, hex colors, and `rgb()/rgba()` calls should all be
   colored.

## What it provides

- **Language registration** for `.crl` (id: `circlelib`), with
  comment markers (`//`, `/* */`) and bracket auto-closing.
- **TextMate grammar** covering:
  - Keywords: `import`, `as`, `component`, `scene`, `Group`
  - Built-in primitives: `Cube`, `Sphere`, `Cylinder`, `Circle`,
    `Plane`, `Cone`
  - Color helpers: `rgb`, `rgba`, hex literals (`#rgb` and `#rrggbb`)
  - Numbers, strings, operators, `alias.Name` member access.
- **Snippets** for: `scene`, `component`, `import`, `cube`, `sphere`,
  `cylinder`, `circle`, `plane`, `cone`, `group`.

## Layout

```
tools/vscode-circlelib/
├── package.json                   # extension manifest
├── language-configuration.json    # comments / bracket pairs
├── syntaxes/circlelib.tmLanguage.json
└── snippets/circlelib.json
```

## Publishing

Out of scope for v0.2. The extension lives inside the main repo so
contributors can iterate on the grammar alongside the language itself.
