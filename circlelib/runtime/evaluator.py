"""Evaluate a loaded program into renderable SceneNodes.

The evaluator runs in two phases:

1. **Static pass** — walks the entry scene once and produces a list
   of ``_LeafState`` records. Each leaf carries the mesh, the parent
   transform composed from enclosing Groups / components, and a copy
   of the call's keyword arguments (position, rotation, color, …).
2. **Frame pass** — given a time value `t`, applies any matching
   `animate { label.attr = expr }` overrides to a leaf's args, rebuilds
   its local transform, and emits a ``SceneNode``.

For scenes without an ``animate { ... }`` block the frame pass simply
emits the same nodes every call. For animated scenes the renderer
calls ``compile_program(program)(t)`` per frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from pyrr import Matrix44, Quaternion, Vector3

from circlelib.ast.nodes import (
    AnimCall,
    Animate,
    AnimateRule,
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
    RgbCall,
    Scene,
    StringLit,
    TupleLit,
    UnaryOp,
)
from circlelib.runtime import primitives
from circlelib.runtime.colors import lookup_named_color
from circlelib.runtime.easing import resolve_easing
from circlelib.runtime.resolver import LoadedProgram


DEFAULT_COLOR: Tuple[float, float, float] = (0.85, 0.85, 0.9)


@dataclass
class SceneNode:
    vertices: np.ndarray
    indices: np.ndarray
    normals: np.ndarray
    transform: np.ndarray  # 4x4 float32, column-major (pyrr default)
    color: Tuple[float, float, float]
    alpha: float = 1.0


@dataclass
class _LeafState:
    """Static-time descriptor for one rendered primitive instance.

    Mesh data is fixed for v0.3. ``parent_transform`` is the world
    transform composed by enclosing Groups / components. ``local_args``
    is a copy of the call's evaluated keyword args; the frame pass
    overrides ``position`` / ``rotation`` / ``color`` from animate
    rules and rebuilds the local transform on top of it.
    """

    vertices: np.ndarray
    indices: np.ndarray
    normals: np.ndarray
    parent_transform: np.ndarray
    local_args: Dict[str, object]
    label: Optional[str] = None


class EvalError(RuntimeError):
    pass


# Builtins ----------------------------------------------------------
# Each builtin returns just the mesh `(verts, indices, normals)` tuple.
# The leaf's transform / color is composed at frame time from the
# call's `local_args` (potentially overridden by an animate rule).

def _builtin_cube(args: dict):
    return primitives.cube(
        _need_number(args, "width", "Cube"),
        _need_number(args, "height", "Cube"),
        _need_number(args, "depth", "Cube"),
    )


def _builtin_sphere(args: dict):
    return primitives.sphere(_need_number(args, "radius", "Sphere"))


def _builtin_cylinder(args: dict):
    return primitives.cylinder(
        _need_number(args, "radius", "Cylinder"),
        _need_number(args, "height", "Cylinder"),
    )


def _builtin_circle(args: dict):
    radius = _need_number(args, "radius", "Circle")
    tube = args.get("tube")
    if tube is None:
        tube = radius * 0.1
    elif not isinstance(tube, (int, float)):
        raise EvalError("Circle: 'tube' must be a number")
    return primitives.torus(radius, float(tube))


def _builtin_plane(args: dict):
    return primitives.plane(
        _need_number(args, "width", "Plane"),
        _need_number(args, "depth", "Plane"),
    )


def _builtin_cone(args: dict):
    return primitives.cone(
        _need_number(args, "radius", "Cone"),
        _need_number(args, "height", "Cone"),
    )


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


def _leaf_to_scene_node(leaf: _LeafState, frame_args: dict) -> SceneNode:
    """Build a renderable ``SceneNode`` from a leaf and its frame-time args.

    ``frame_args`` is typically ``leaf.local_args`` plus any animate
    overrides for ``position`` / ``rotation`` / ``color``. Only those
    three fields are honored at frame time in v0.3.
    """
    raw = frame_args.get("color", DEFAULT_COLOR)
    if not isinstance(raw, tuple) or len(raw) not in (3, 4):
        raise EvalError(
            "'color' must be a hex literal, rgb()/rgba(), a named CSS "
            "color, or a 3-/4-tuple"
        )
    if len(raw) == 4:
        color = (float(raw[0]), float(raw[1]), float(raw[2]))
        alpha = float(raw[3])
    else:
        color = (float(raw[0]), float(raw[1]), float(raw[2]))
        alpha = 1.0
    local = _local_transform(frame_args)
    transform = np.array(leaf.parent_transform @ local, dtype="f4")
    return SceneNode(
        vertices=leaf.vertices,
        indices=leaf.indices,
        normals=leaf.normals,
        transform=transform,
        color=color,
        alpha=alpha,
    )


# Evaluator ---------------------------------------------------------

@dataclass
class _EvalCtx:
    program: LoadedProgram
    current_path: Path
    component_stack: List[str] = field(default_factory=list)
    component_env_stack: List[Dict[str, object]] = field(default_factory=list)
    module_envs: Dict[Path, Dict[str, object]] = field(default_factory=dict)
    time: Optional[float] = None  # bound only inside frame_pass

    def lookup(self, name: str):
        # Innermost component scope first, then the current module env,
        # finally the CSS named-color table (so `color=red` works).
        for scope in reversed(self.component_env_stack):
            if name in scope:
                return scope[name]
        module_env = self.module_envs.get(self.current_path, {})
        if name in module_env:
            return module_env[name]
        if name == "t" and self.time is not None:
            return self.time
        named = lookup_named_color(name)
        if named is not None:
            return named
        raise EvalError(f"undefined name: {name}")


@dataclass
class CompiledScene:
    """Result of `compile_program`. Callable returns a SceneNode list
    for a given time `t` (seconds). For non-animated scenes it returns
    the same precomputed list every call.
    """

    leaves: List[_LeafState]
    rules_by_label: Dict[str, List[AnimateRule]]
    duration: float
    program: LoadedProgram

    def __call__(self, t: float) -> List[SceneNode]:
        return _frame_pass(self, t)

    @property
    def is_animated(self) -> bool:
        return bool(self.rules_by_label)


def compile_program(program: LoadedProgram) -> CompiledScene:
    """Static-pass entry point. Builds a `CompiledScene` callable."""
    if program.entry.scene is None:
        raise EvalError("entry module has no scene block")
    ctx = _EvalCtx(program=program, current_path=program.entry_path)
    _eval_module_bindings(ctx)
    ctx.current_path = program.entry_path

    leaves: List[_LeafState] = []
    ctx.component_env_stack.append({})
    try:
        for stmt in program.entry.scene.body:
            _eval_stmt(stmt, ctx, _identity(), leaves, label=None)
    finally:
        ctx.component_env_stack.pop()

    rules_by_label: Dict[str, List[AnimateRule]] = {}
    duration = 0.0
    animate = program.entry.animate
    if animate is not None:
        ctx.time = None  # `t` undefined while computing duration
        d_val = _eval_expr(animate.duration, ctx)
        if not isinstance(d_val, (int, float)) or d_val <= 0:
            raise EvalError("animate { duration = ... } must be a positive number")
        duration = float(d_val)
        for rule in animate.rules:
            rules_by_label.setdefault(rule.label, []).append(rule)
        # Sanity: every animate rule must reference a labelled leaf.
        known_labels = {leaf.label for leaf in leaves if leaf.label is not None}
        for label in rules_by_label:
            if label not in known_labels:
                raise EvalError(
                    f"animate rule references unknown label '{label}' — "
                    f"label leaves with `name = Cube(...)` etc. in the scene"
                )

    return CompiledScene(
        leaves=leaves,
        rules_by_label=rules_by_label,
        duration=duration,
        program=program,
    )


def _frame_pass(scene: CompiledScene, t: float) -> List[SceneNode]:
    if not scene.rules_by_label:
        # Static path: no animate block, just convert each leaf with
        # its captured args.
        return [_leaf_to_scene_node(leaf, leaf.local_args) for leaf in scene.leaves]

    ctx = _EvalCtx(program=scene.program, current_path=scene.program.entry_path)
    _eval_module_bindings(ctx)
    ctx.current_path = scene.program.entry_path
    ctx.time = float(t)
    ctx.component_env_stack.append({})
    try:
        out: List[SceneNode] = []
        for leaf in scene.leaves:
            args = dict(leaf.local_args)
            rules = scene.rules_by_label.get(leaf.label or "", [])
            for rule in rules:
                args[rule.attr] = _eval_expr(rule.value, ctx)
            out.append(_leaf_to_scene_node(leaf, args))
        return out
    finally:
        ctx.component_env_stack.pop()


def evaluate(program: LoadedProgram) -> List[SceneNode]:
    """Backward-compat one-shot evaluation at t = 0.0.

    For animated scenes call ``compile_program(program)`` and invoke
    the result with the current time instead.
    """
    return compile_program(program)(0.0)


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


def _eval_stmt(
    stmt,
    ctx: _EvalCtx,
    parent: np.ndarray,
    out: List[_LeafState],
    label: Optional[str] = None,
) -> None:
    if isinstance(stmt, Call):
        _eval_call(stmt, ctx, parent, out, label=label)
    elif isinstance(stmt, Assignment):
        # If the rhs is a renderable call (builtin or component), expand
        # it as a child of the current scope and remember the
        # assignment name as the leaf's label so animate rules can
        # target it.  Otherwise the rhs is a plain value expression —
        # bind it into the innermost env.
        if isinstance(stmt.value, Call):
            _eval_call(stmt.value, ctx, parent, out, label=stmt.name)
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


def _eval_call(
    call: Call,
    ctx: _EvalCtx,
    parent: np.ndarray,
    out: List[_LeafState],
    label: Optional[str] = None,
) -> None:
    args = _eval_args(call.args, ctx)
    if isinstance(call.callee, Identifier):
        name = call.callee.name
        if name in BUILTINS:
            verts, indices, normals = BUILTINS[name](args)
            out.append(
                _LeafState(
                    vertices=verts,
                    indices=indices,
                    normals=normals,
                    parent_transform=parent.copy(),
                    local_args=args,
                    label=label,
                )
            )
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
    out: List[_LeafState],
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
    if isinstance(expr, RgbCall):
        return _eval_rgb_call(expr, ctx)
    if isinstance(expr, AnimCall):
        return _eval_anim_call(expr, ctx)
    if isinstance(expr, Call):
        # Evaluating a call as an argument value is unsupported in v0.1.
        raise EvalError("nested calls as argument values are not supported")
    raise EvalError(f"cannot evaluate expression: {type(expr).__name__}")


def _eval_anim_call(node: AnimCall, ctx: _EvalCtx):
    t_val = _eval_expr(node.t, ctx)
    if not isinstance(t_val, (int, float)):
        raise EvalError("anim(): first argument must be a number (typically `t`)")
    start = _eval_expr(node.start, ctx)
    end = _eval_expr(node.end, ctx)
    duration = _eval_expr(node.duration, ctx)
    if not isinstance(duration, (int, float)):
        raise EvalError("anim(): duration must be a number")
    fn = resolve_easing(node.easing)
    if fn is None:
        raise EvalError(f"anim(): unknown easing '{node.easing}'")
    if duration <= 0:
        return end
    progress = max(0.0, min(1.0, float(t_val) / float(duration)))
    eased = fn(progress)
    return _lerp(start, end, eased)


def _lerp(a, b, t: float):
    if isinstance(a, tuple) and isinstance(b, tuple):
        if len(a) != len(b):
            raise EvalError("anim(): tuple endpoints have mismatched lengths")
        return tuple(_lerp(x, y, t) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return (1.0 - t) * float(a) + t * float(b)
    raise EvalError("anim(): endpoints must be numbers or tuples of numbers")


def _eval_rgb_call(expr: RgbCall, ctx: _EvalCtx):
    values = tuple(_eval_expr(c, ctx) for c in expr.components)
    for v in values:
        if not isinstance(v, (int, float)):
            raise EvalError("rgb()/rgba() arguments must be numbers")
    if len(values) == 3:
        return (values[0] / 255.0, values[1] / 255.0, values[2] / 255.0)
    if len(values) == 4:
        return (
            values[0] / 255.0,
            values[1] / 255.0,
            values[2] / 255.0,
            float(values[3]),
        )
    raise EvalError("rgb()/rgba() must take 3 or 4 arguments")


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
