"""Evaluate a loaded program into a flat list of SceneNodes.

A SceneNode is a leaf with a mesh + a world-space transform + a color.
Components are inlined (their bodies expand) at evaluation time. Group
blocks compose transforms onto their children.

This evaluator is intentionally simple: no animations, no expressions
beyond literals/identifiers. The structure leaves room for an
``animate`` pass and richer expressions later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from pyrr import Matrix44, Quaternion, Vector3

from circlelib.ast.nodes import (
    Argument,
    Assignment,
    Call,
    ColorLit,
    Component,
    GroupBlock,
    Identifier,
    MemberAccess,
    Module,
    NumberLit,
    Scene,
    StringLit,
    TupleLit,
)
from circlelib.runtime import primitives
from circlelib.runtime.resolver import LoadedProgram


DEFAULT_COLOR: Tuple[float, float, float] = (0.85, 0.85, 0.9)


@dataclass
class SceneNode:
    vertices: np.ndarray
    indices: np.ndarray
    normals: np.ndarray
    transform: np.ndarray  # 4x4 float32, column-major (pyrr default)
    color: Tuple[float, float, float]


class EvalError(RuntimeError):
    pass


# Builtins ----------------------------------------------------------

def _builtin_cube(args: dict) -> "SceneNode":
    v, i, n = primitives.cube(
        _need_number(args, "width", "Cube"),
        _need_number(args, "height", "Cube"),
        _need_number(args, "depth", "Cube"),
    )
    return _make_leaf(v, i, n, args)


def _builtin_sphere(args: dict) -> "SceneNode":
    v, i, n = primitives.sphere(_need_number(args, "radius", "Sphere"))
    return _make_leaf(v, i, n, args)


def _builtin_cylinder(args: dict) -> "SceneNode":
    v, i, n = primitives.cylinder(
        _need_number(args, "radius", "Cylinder"),
        _need_number(args, "height", "Cylinder"),
    )
    return _make_leaf(v, i, n, args)


def _builtin_circle(args: dict) -> "SceneNode":
    radius = _need_number(args, "radius", "Circle")
    tube = args.get("tube")
    if tube is None:
        tube = radius * 0.1
    elif not isinstance(tube, (int, float)):
        raise EvalError("Circle: 'tube' must be a number")
    v, i, n = primitives.torus(radius, float(tube))
    return _make_leaf(v, i, n, args)


BUILTINS = {
    "Cube": _builtin_cube,
    "Sphere": _builtin_sphere,
    "Cylinder": _builtin_cylinder,
    "Circle": _builtin_circle,
}


# Helpers -----------------------------------------------------------

def _need_number(args: dict, key: str, who: str) -> float:
    if key not in args:
        raise EvalError(f"{who} requires keyword argument '{key}'")
    val = args[key]
    if not isinstance(val, (int, float)):
        raise EvalError(f"{who}: argument '{key}' must be a number")
    return float(val)


def _identity() -> np.ndarray:
    return np.array(Matrix44.identity(dtype="f4"), dtype="f4")


def _local_transform(args: dict) -> np.ndarray:
    m = Matrix44.identity(dtype="f4")
    rot = args.get("rotation")
    if rot is not None:
        if not (isinstance(rot, tuple) and len(rot) == 3):
            raise EvalError("'rotation' must be a 3-tuple of degrees")
        rx, ry, rz = (float(x) for x in rot)
        q = (
            Quaternion.from_x_rotation(np.deg2rad(rx))
            * Quaternion.from_y_rotation(np.deg2rad(ry))
            * Quaternion.from_z_rotation(np.deg2rad(rz))
        )
        m = Matrix44.from_quaternion(q, dtype="f4") * m
    pos = args.get("position")
    if pos is not None:
        if not (isinstance(pos, tuple) and len(pos) == 3):
            raise EvalError("'position' must be a 3-tuple")
        m = Matrix44.from_translation(Vector3([float(p) for p in pos]), dtype="f4") * m
    return np.array(m, dtype="f4")


def _make_leaf(verts, indices, normals, args: dict) -> SceneNode:
    color = args.get("color", DEFAULT_COLOR)
    if not (isinstance(color, tuple) and len(color) == 3):
        raise EvalError("'color' must be a hex literal like #rrggbb")
    return SceneNode(
        vertices=verts,
        indices=indices,
        normals=normals,
        transform=_local_transform(args),
        color=color,
    )


# Evaluator ---------------------------------------------------------

@dataclass
class _EvalCtx:
    program: LoadedProgram
    current_path: Path
    component_stack: List[str] = field(default_factory=list)


def evaluate(program: LoadedProgram) -> List[SceneNode]:
    if program.entry.scene is None:
        raise EvalError("entry module has no scene block")
    ctx = _EvalCtx(program=program, current_path=program.entry_path)
    nodes: list[SceneNode] = []
    for stmt in program.entry.scene.body:
        _eval_stmt(stmt, ctx, _identity(), nodes)
    return nodes


def _eval_stmt(stmt, ctx: _EvalCtx, parent: np.ndarray, out: List[SceneNode]) -> None:
    if isinstance(stmt, Call):
        _eval_call(stmt, ctx, parent, out)
    elif isinstance(stmt, Assignment):
        # In a scene/component body, an assignment is just a named call.
        # We treat the rhs as if the name were the binding label and
        # render the value if it is a call. (Names are not yet
        # referenceable; this is a future feature.)
        if isinstance(stmt.value, Call):
            _eval_call(stmt.value, ctx, parent, out)
        else:
            raise EvalError(
                f"assignment '{stmt.name}' must bind a component or primitive call"
            )
    elif isinstance(stmt, GroupBlock):
        local = _local_transform(_eval_args(stmt.args, ctx))
        combined = np.array(parent @ local, dtype="f4")
        for child in stmt.body:
            _eval_stmt(child, ctx, combined, out)
    else:
        raise EvalError(f"unsupported statement: {type(stmt).__name__}")


def _eval_call(call: Call, ctx: _EvalCtx, parent: np.ndarray, out: List[SceneNode]) -> None:
    args = _eval_args(call.args, ctx)
    if isinstance(call.callee, Identifier):
        name = call.callee.name
        if name in BUILTINS:
            leaf = BUILTINS[name](args)
            leaf.transform = np.array(parent @ leaf.transform, dtype="f4")
            out.append(leaf)
            return
        component = _find_component(ctx.current_path, name, ctx.program)
        if component is None:
            raise EvalError(f"unknown component or primitive: {name}")
        _expand_component(component, args, ctx, ctx.current_path, parent, out)
        return

    if isinstance(call.callee, MemberAccess):
        if len(call.callee.parts) != 2:
            raise EvalError(
                "only single-level alias references (alias.Name) are supported"
            )
        alias, name = call.callee.parts
        aliases = ctx.program.alias_tables.get(ctx.current_path, {})
        if alias not in aliases:
            raise EvalError(f"unknown import alias: {alias}")
        target_module = aliases[alias]
        target_path = _path_for_module(target_module, ctx.program)
        component = _find_component_in(target_module, name)
        if component is None:
            raise EvalError(f"module '{alias}' has no component '{name}'")
        _expand_component(component, args, ctx, target_path, parent, out)
        return

    raise EvalError("unsupported callee form")


def _expand_component(
    component: Component,
    args: dict,
    ctx: _EvalCtx,
    component_path: Path,
    parent: np.ndarray,
    out: List[SceneNode],
) -> None:
    if component.name in ctx.component_stack:
        raise EvalError(
            "recursive component instantiation: "
            + " -> ".join(ctx.component_stack + [component.name])
        )
    local = _local_transform(args)
    combined = np.array(parent @ local, dtype="f4")
    ctx.component_stack.append(component.name)
    saved_path = ctx.current_path
    ctx.current_path = component_path
    try:
        for stmt in component.body:
            _eval_stmt(stmt, ctx, combined, out)
    finally:
        ctx.component_stack.pop()
        ctx.current_path = saved_path


def _eval_args(args: Tuple[Argument, ...], ctx: _EvalCtx) -> Dict[str, object]:
    out: dict[str, object] = {}
    for a in args:
        out[a.name] = _eval_expr(a.value, ctx)
    return out


def _eval_expr(expr, ctx: _EvalCtx):
    if isinstance(expr, NumberLit):
        return expr.value
    if isinstance(expr, StringLit):
        return expr.value
    if isinstance(expr, ColorLit):
        return expr.rgb
    if isinstance(expr, TupleLit):
        return tuple(_eval_expr(it, ctx) for it in expr.items)
    if isinstance(expr, (Identifier, MemberAccess)):
        # Bare identifier in argument position is currently unsupported.
        raise EvalError("identifiers as argument values are not yet supported")
    if isinstance(expr, Call):
        # Evaluating a call as an argument value is unsupported in v0.1.
        raise EvalError("nested calls as argument values are not supported")
    raise EvalError(f"cannot evaluate expression: {type(expr).__name__}")


def _find_component(path: Path, name: str, program: LoadedProgram) -> Optional[Component]:
    module = program.modules.get(path)
    if module is None:
        return None
    return _find_component_in(module, name)


def _find_component_in(module: Module, name: str) -> Optional[Component]:
    for c in module.components:
        if c.name == name:
            return c
    return None


def _path_for_module(module: Module, program: LoadedProgram) -> Path:
    for path, m in program.modules.items():
        if m is module:
            return path
    raise EvalError("module not found in program (internal error)")
