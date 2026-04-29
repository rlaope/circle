"""Module loader that walks `import` statements relative to a base file.

`load(entry_path)` returns a `LoadedProgram` containing:
- the entry module's AST
- a mapping {alias -> Module} for everything imported (transitively)

Three import path forms are recognised:

- `@stdlib/<sub>` resolves into the catalog shipped at
  `circlelib/stdlib/<sub>.crl`.
- `@<owner>/<repo>/<sub>` (any `<owner>` other than `stdlib`) resolves
  into `<CIRCLELIB_HOME>/packages/<owner>/<repo>/<sub>.crl`. The
  install command (`circlelib install`) is what populates this cache.
- Everything else is resolved relative to the importing file's directory.

A `.crl` extension is auto-appended if missing. Circular imports raise.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from circlelib.ast.nodes import Module
from circlelib.parser import parse_file


STDLIB_PREFIX = "@stdlib/"
STDLIB_ROOT = Path(__file__).resolve().parent.parent / "stdlib"


def circlelib_home() -> Path:
    """Root directory for the third-party package cache.

    Honours `$CIRCLELIB_HOME` if set; otherwise `~/.circlelib`. Resolved
    on every call so tests can override the env var per test case.
    """
    raw = os.environ.get("CIRCLELIB_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".circlelib").resolve()


def packages_root() -> Path:
    return circlelib_home() / "packages"


class PackageNotInstalledError(RuntimeError):
    pass


@dataclass
class LoadedProgram:
    entry_path: Path
    entry: Module
    # Per-module alias tables: file path -> {alias -> imported Module}.
    # This lets the evaluator look up which module an alias refers to from
    # whatever file it is currently evaluating.
    alias_tables: Dict[Path, Dict[str, Module]] = field(default_factory=dict)
    # Path -> Module, useful for diagnostics and tests.
    modules: Dict[Path, Module] = field(default_factory=dict)


class CircularImportError(RuntimeError):
    pass


def _resolve_path(base: Path, raw: str) -> Path:
    if raw.startswith(STDLIB_PREFIX):
        sub = raw[len(STDLIB_PREFIX):]
        target = (STDLIB_ROOT / sub).resolve()
    elif raw.startswith("@"):
        # @<owner>/<repo>/<sub> — third-party package cache.
        rest = raw[1:]
        parts = rest.split("/", 2)
        if len(parts) < 3 or not all(parts[:2]):
            raise PackageNotInstalledError(
                f"invalid package import '{raw}'. Expected "
                f"'@<owner>/<repo>/<sub>' (e.g. '@me/pkg/foo')."
            )
        owner, repo, sub = parts
        pkg_root = packages_root() / owner / repo
        if not pkg_root.is_dir():
            raise PackageNotInstalledError(
                f"package '@{owner}/{repo}' is not installed. Run "
                f"`circlelib install {owner}/{repo}` (or "
                f"`circlelib install --from <dir> {owner}/{repo}` for a "
                f"local install)."
            )
        target = (pkg_root / sub).resolve()
    else:
        target = (base.parent / raw).resolve()
    if target.suffix == "":
        target = target.with_suffix(".crl")
    return target


def load(entry_path: str | Path) -> LoadedProgram:
    entry = Path(entry_path).resolve()
    program = LoadedProgram(entry_path=entry, entry=Module())

    in_progress: set[Path] = set()

    def _load(path: Path) -> Module:
        if path in in_progress:
            raise CircularImportError(f"circular import detected at {path}")
        if path in program.modules:
            return program.modules[path]
        if not path.exists():
            raise FileNotFoundError(f"module not found: {path}")
        in_progress.add(path)
        module = parse_file(path)
        program.modules[path] = module
        aliases: dict[str, Module] = {}
        for imp in module.imports:
            target = _resolve_path(path, imp.path)
            aliases[imp.alias] = _load(target)
        program.alias_tables[path] = aliases
        in_progress.discard(path)
        return module

    program.entry = _load(entry)
    return program
