"""AST node definitions for the circlelib DSL.

Nodes are plain dataclasses so they are trivially comparable in tests
and easy to walk in the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


Expr = Union[
    "NumberLit",
    "StringLit",
    "ColorLit",
    "RgbCall",
    "TupleLit",
    "Identifier",
    "MemberAccess",
    "Call",
    "BinaryOp",
    "UnaryOp",
]


@dataclass(frozen=True)
class NumberLit:
    value: float


@dataclass(frozen=True)
class StringLit:
    value: str


@dataclass(frozen=True)
class ColorLit:
    # Stored as (r, g, b) floats in [0, 1].
    rgb: Tuple[float, float, float]


@dataclass(frozen=True)
class RgbCall:
    # 3 expressions for rgb(r, g, b); 4 for rgba(r, g, b, a).
    components: Tuple["Expr", ...]


@dataclass(frozen=True)
class TupleLit:
    items: Tuple[Expr, ...]


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class MemberAccess:
    # E.g. wheels.Pair  ->  MemberAccess(parts=("wheels", "Pair"))
    parts: Tuple[str, ...]


@dataclass(frozen=True)
class Argument:
    name: str
    value: Expr


@dataclass(frozen=True)
class Call:
    callee: Union[Identifier, MemberAccess]
    args: Tuple[Argument, ...]


@dataclass(frozen=True)
class BinaryOp:
    op: str  # one of "+", "-", "*", "/", "%"
    left: Expr
    right: Expr


@dataclass(frozen=True)
class UnaryOp:
    op: str  # currently only "-"
    operand: Expr


@dataclass
class Assignment:
    name: str
    value: Expr


@dataclass
class GroupBlock:
    args: Tuple[Argument, ...]
    body: List["Statement"]


Statement = Union[Assignment, Call, GroupBlock]


@dataclass
class Component:
    name: str
    body: List[Statement]


@dataclass
class Scene:
    body: List[Statement]


@dataclass
class Import:
    path: str
    alias: str


@dataclass
class Module:
    imports: List[Import] = field(default_factory=list)
    components: List[Component] = field(default_factory=list)
    bindings: List[Assignment] = field(default_factory=list)
    scene: Optional[Scene] = None
