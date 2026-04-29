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
    BinaryOp,
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
    UnaryOp,
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


def _builtin_plane(args: dict) -> "SceneNode":
    v, i, n = primitives.plane(
        _need_number(args, "width", "Plane"),
        _need_number(args, "depth", "Plane"),
    )
    return _make_leaf(v, i, n, args)


def _builtin_cone(args: dict) -> "SceneNode":
    v, i, n = primitives.cone(
        _need_number(args, "radius", "Cone"),
        _need_number(args, "height", "Cone"),
    )
    return _make_leaf(v, i, n, args)


BUILTINS = {
    "Cube": _builtin_cube,
    "Sphere": _builtin_sphere,
    "Cylinder": _builtin_cylinder,
    "Circle": _builtin_circle,
    "Plane": _builtin_plane,
    "Cone": _builtin_cone,
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
    component_env_stack: List[Dict[str, object]] = field(default_factory=list)
    module_envs: Dict[Path, Dict[str, object]] = field(default_factory=dict)

    def lookup(self, name: str):
        # Innermost component scope first, then the current module env.
        for scope in reversed(self.component_env_stack):
            if name in scope:
                return scope[name]
        module_env = self.module_envs.get(self.current_path, {})
        if name in module_env:
            return module_env[name]
        raise EvalError(f"undefined name: {name}")


def evaluate(program: LoadedProgram) -> List[SceneNode]:
    if program.entry.scene is None:
        raise EvalError("entry module has no scene block")
    ctx = _EvalCtx(program=program, current_path=program.entry_path)
    _eval_module_bindings(ctx)
    ctx.current_path = program.entry_path
    nodes: list[SceneNode] = []
    ctx.component_env_stack.append({})
    try:
        for stmt in program.entry.scene.body:
            _eval_stmt(stmt, ctx, _identity(), nodes)
    finally:
        ctx.component_env_stack.pop()
    return nodes


def _eval_module_bindings(ctx: _EvalCtx) -> None:
    # Each module gets its own top-level env. Bindings can reference
    # earlier bindings in the same module; cross-module references go
    # through `import ... as` aliases (not via top-level identifiers).
    for path, module in ctx.program.modules.items():
        env: Dict[str, object] = {}
        ctx.module_envs[path] = env
        ctx.current_path = path
        for binding in module.bindings:
            env[binding.name] = _eval_expr(binding.value, ctx)


def _eval_stmt(stmt, ctx: _EvalCtx, parent: np.ndarray, out: List[SceneNode]) -> None:
    if isinstance(stmt, Call):
        _eval_call(stmt, ctx, parent, out)
    elif isinstance(stmt, Assignment):
        # If the rhs is a renderable call (builtin or component), expand
        # it as a child of the current scope; the name is just a label.
        # Otherwise the rhs is a value expression — bind it into the
        # innermost env so later identifiers can resolve it.
        if isinstance(stmt.value, Call):
            _eval_call(stmt.value, ctx, parent, out)
        else:
            value = _eval_expr(stmt.value, ctx)
            if not ctx.component_env_stack:
                raise EvalError(
                    f"binding '{stmt.name}' must live at module top level "
                    f"or inside a component body"
                )
            ctx.component_env_stack[-1][stmt.name] = value
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
    ctx.component_env_stack.append({})
    try:
        for stmt in component.body:
            _eval_stmt(stmt, ctx, combined, out)
    finally:
        ctx.component_env_stack.pop()
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
    if isinstance(expr, Identifier):
        return ctx.lookup(expr.name)
    if isinstance(expr, MemberAccess):
        raise EvalError("module.alias access is not allowed in expression positions")
    if isinstance(expr, BinaryOp):
        return _apply_binop(expr.op, _eval_expr(expr.left, ctx), _eval_expr(expr.right, ctx))
    if isinstance(expr, UnaryOp):
        return _apply_unaryop(expr.op, _eval_expr(expr.operand, ctx))
    if isinstance(expr, Call):
        # Evaluating a call as an argument value is unsupported in v0.1.
        raise EvalError("nested calls as argument values are not supported")
    raise EvalError(f"cannot evaluate expression: {type(expr).__name__}")


def _apply_binop(op: str, left, right):
    # Tuple component-wise arithmetic when both sides are tuples of equal length.
    if isinstance(left, tuple) and isinstance(right, tuple):
        if len(left) != len(right):
            raise EvalError(
                f"tuple {op} between mismatched lengths {len(left)} and {len(right)}"
            )
        return tuple(_apply_binop(op, a, b) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise EvalError("division by zero")
            return left / right
        if op == "%":
            if right == 0:
                raise EvalError("modulo by zero")
            return left % right
    raise EvalError(
        f"unsupported operands for '{op}': {type(left).__name__} and {type(right).__name__}"
    )


def _apply_unaryop(op: str, value):
    if op == "-":
        if isinstance(value, (int, float)):
            return -value
        if isinstance(value, tuple):
            return tuple(_apply_unaryop("-", v) for v in value)
        raise EvalError(f"unary - not supported on {type(value).__name__}")
    raise EvalError(f"unknown unary operator: {op}")


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
