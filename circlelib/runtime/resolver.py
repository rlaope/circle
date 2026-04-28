"""Module loader that walks `import` statements relative to a base file.

`load(entry_path)` returns a `LoadedProgram` containing:
- the entry module's AST
- a mapping {alias -> Module} for everything imported (transitively)

Imports are resolved relative to the importing file's directory.
A `.crl` extension is auto-appended if missing. Circular imports raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from circlelib.ast.nodes import Module
from circlelib.parser import parse_file


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
