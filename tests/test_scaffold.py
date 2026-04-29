"""Tests for `circlelib new` scaffolder.

Each template must produce a `.crl` that the parser + evaluator
accept. The `stdlib` template additionally exercises the `@stdlib/`
import prefix end-to-end via the resolver.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from circlelib.runtime.evaluator import compile_program
from circlelib.runtime.resolver import load
from circlelib.runtime.scaffold import (
    ScaffoldError,
    list_templates,
    write_scaffold,
)


def _compile(path: Path):
    program = load(path)
    return compile_program(program)


def test_default_template_parses_and_evaluates(tmp_path):
    out = write_scaffold(tmp_path / "blank")
    assert out.suffix == ".crl"
    assert out.exists()
    nodes = _compile(out)(0.0)
    # Default template renders 1 sphere + 1 cube under a Group.
    assert len(nodes) == 2


def test_anim_template_has_animate_block(tmp_path):
    out = write_scaffold(tmp_path / "spin", template="anim")
    compiled = _compile(out)
    assert compiled.is_animated is True
    assert compiled.duration == 4.0
    # Single labelled sphere in the scene.
    assert len(compiled(0.0)) == 1
    # Position interpolates from start to end.
    nodes_start = compiled(0.0)
    nodes_end = compiled(compiled.duration)
    assert nodes_start[0].transform[3, 0] != nodes_end[0].transform[3, 0]


def test_stdlib_template_resolves_stdlib_imports(tmp_path):
    out = write_scaffold(tmp_path / "scene", template="stdlib")
    nodes = _compile(out)(0.0)
    # Axes (3 cylinders + 1 sphere = 4) + Chair (4 legs + seat + back = 6) = 10.
    assert len(nodes) == 10


def test_default_template_used_when_template_omitted(tmp_path):
    out = write_scaffold(tmp_path / "x")
    text = out.read_text()
    # Default has the two-primitive Group; anim has animate{}.
    assert "Group" in text
    assert "animate" not in text


def test_extension_auto_appended_when_omitted(tmp_path):
    out = write_scaffold(tmp_path / "noext")
    assert out.suffix == ".crl"


def test_existing_extension_is_preserved(tmp_path):
    out = write_scaffold(tmp_path / "stays.crl")
    # Auto-appender must not double up the extension.
    assert out.name == "stays.crl"


def test_does_not_overwrite_by_default(tmp_path):
    target = tmp_path / "exists.crl"
    target.write_text("// hand-written, do not lose me\n")
    with pytest.raises(ScaffoldError):
        write_scaffold(target)
    assert "do not lose me" in target.read_text()


def test_force_overwrites(tmp_path):
    target = tmp_path / "exists.crl"
    target.write_text("// stale\n")
    write_scaffold(target, force=True)
    assert "circlelib new" in target.read_text()


def test_unknown_template_raises(tmp_path):
    with pytest.raises(ScaffoldError):
        write_scaffold(tmp_path / "x", template="nosuch")


def test_list_templates_returns_known_ids():
    names = list_templates()
    assert {"default", "anim", "stdlib"}.issubset(set(names))


def test_parent_directory_is_created(tmp_path):
    nested = tmp_path / "a" / "b" / "c" / "scene.crl"
    out = write_scaffold(nested)
    assert out.exists()


def test_brace_in_filename_does_not_break_substitution(tmp_path):
    # Earlier draft used .format() on the templates, which would crash
    # if the file stem contained `{` or `}`. The implementation now
    # uses .replace() so this is robust to unusual stems.
    out = write_scaffold(tmp_path / "weird{name}")
    assert out.exists()
    text = out.read_text()
    # Stem appears verbatim in the comment header.
    assert "weird{name}" in text
    # The .crl still parses + evaluates.
    nodes = _compile(out)(0.0)
    assert len(nodes) == 2
