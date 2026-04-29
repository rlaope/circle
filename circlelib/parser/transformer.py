"""Lark parser + tree transformer for the circlelib DSL.

`parse_source` parses a string of `.crl` source into a `Module` AST.
`parse_file` does the same starting from a path.
"""

from __future__ import annotations

from pathlib import Path

from lark import Lark, Transformer, v_args

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
    Import,
    MemberAccess,
    Module,
    NumberLit,
    RgbCall,
    Scene,
    StringLit,
    TupleLit,
    UnaryOp,
)


_GRAMMAR_PATH = Path(__file__).resolve().parent.parent / "grammar" / "circle.lark"


def _build_parser() -> Lark:
    grammar = _GRAMMAR_PATH.read_text(encoding="utf-8")
    return Lark(grammar, parser="earley", maybe_placeholders=False)


_PARSER: Lark | None = None


def _parser() -> Lark:
    global _PARSER
    if _PARSER is None:
        _PARSER = _build_parser()
    return _PARSER


def _hex_to_rgb(token: str) -> tuple[float, float, float]:
    s = token.lstrip("#")
    if len(s) == 3:
        # CSS shorthand: #rgb -> #rrggbb (each digit doubled).
        s = "".join(c * 2 for c in s)
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return (r, g, b)


@v_args(inline=True)
class _ToAst(Transformer):
    # Literals -------------------------------------------------------

    def number_lit(self, tok):
        return NumberLit(float(tok))

    def string_lit(self, tok):
        # Strip surrounding quotes from ESCAPED_STRING.
        raw = str(tok)
        return StringLit(raw[1:-1])

    def color_lit(self, tok):
        return ColorLit(_hex_to_rgb(str(tok)))

    def rgb3(self, r, g, b):
        return RgbCall(components=(r, g, b))

    def rgb4(self, r, g, b, a):
        return RgbCall(components=(r, g, b, a))

    def anim4(self, t, start, end, duration):
        return AnimCall(t=t, start=start, end=end, duration=duration, easing="linear")

    def anim5(self, t, start, end, duration, easing_name):
        return AnimCall(
            t=t, start=start, end=end, duration=duration,
            easing=str(easing_name),
        )

    def tuple_lit(self, *items):
        return TupleLit(tuple(items))

    # Arithmetic -----------------------------------------------------

    def add(self, left, right):
        return BinaryOp(op="+", left=left, right=right)

    def sub(self, left, right):
        return BinaryOp(op="-", left=left, right=right)

    def mul(self, left, right):
        return BinaryOp(op="*", left=left, right=right)

    def div(self, left, right):
        return BinaryOp(op="/", left=left, right=right)

    def mod(self, left, right):
        return BinaryOp(op="%", left=left, right=right)

    def neg(self, operand):
        return UnaryOp(op="-", operand=operand)

    # Names ----------------------------------------------------------

    def qualified_name(self, *parts):
        names = tuple(str(p) for p in parts)
        if len(names) == 1:
            return Identifier(names[0])
        return MemberAccess(names)

    def ident_expr(self, ref):
        return ref

    # Calls ----------------------------------------------------------

    def call(self, callee, arg_list=None):
        args = tuple(arg_list) if arg_list is not None else ()
        return Call(callee=callee, args=args)

    def call_expr(self, call_node):
        return call_node

    @v_args(inline=False)
    def arg_list(self, items):
        return list(items)

    def arg(self, name, value):
        return Argument(name=str(name), value=value)

    # Statements -----------------------------------------------------

    def assignment(self, name, value):
        return Assignment(name=str(name), value=value)

    def call_stmt(self, call_node):
        return call_node

    def group_stmt(self, *children):
        # children: optional group_args followed by zero or more stmts.
        args: tuple[Argument, ...] = ()
        body: list = []
        for child in children:
            if isinstance(child, list):
                args = tuple(child)
            else:
                body.append(child)
        return GroupBlock(args=args, body=body)

    def group_args(self, arg_list=None):
        return list(arg_list) if arg_list is not None else []

    def stmt(self, child):
        return child

    # Top level ------------------------------------------------------

    def import_stmt(self, path_tok, alias_tok):
        path = str(path_tok)[1:-1]
        return Import(path=path, alias=str(alias_tok))

    def top_binding(self, name, value):
        return Assignment(name=str(name), value=value)

    def component_def(self, name, *body):
        return Component(name=str(name), body=list(body))

    def scene_def(self, *body):
        return Scene(body=list(body))

    def animate_def(self, *items):
        # First pass: pull `duration = expr` binding (must exist exactly
        # once); the rest are AnimateRule instances.
        duration_expr = None
        rules: list[AnimateRule] = []
        for it in items:
            if isinstance(it, AnimateRule):
                rules.append(it)
            elif isinstance(it, tuple) and len(it) == 2 and it[0] == "__binding__":
                _, (name, value) = it
                if name == "duration":
                    if duration_expr is not None:
                        raise SyntaxError(
                            "animate { ... } may only declare 'duration' once"
                        )
                    duration_expr = value
                else:
                    raise SyntaxError(
                        f"animate {{ ... }} only supports 'duration ='; got '{name} ='"
                    )
        if duration_expr is None:
            raise SyntaxError("animate { ... } must declare 'duration = <expr>'")
        return Animate(duration=duration_expr, rules=rules)

    def anim_stmt(self, child):
        return child

    def anim_binding(self, name, value):
        # Sentinel tuple distinguishes module-style bindings from rules.
        return ("__binding__", (str(name), value))

    def anim_rule(self, label, attr, value):
        return AnimateRule(label=str(label), attr=str(attr), value=value)

    def top_item(self, item):
        return item

    @v_args(inline=False)
    def start(self, items):
        module = Module()
        scenes: list[Scene] = []
        animates: list[Animate] = []
        for it in items:
            if isinstance(it, Import):
                module.imports.append(it)
            elif isinstance(it, Component):
                module.components.append(it)
            elif isinstance(it, Scene):
                scenes.append(it)
            elif isinstance(it, Assignment):
                module.bindings.append(it)
            elif isinstance(it, Animate):
                animates.append(it)
        module.scene = scenes[0] if scenes else None
        module.animate = animates[0] if animates else None
        module.__circlelib_scene_count__ = len(scenes)
        module.__circlelib_animate_count__ = len(animates)
        return module


def parse_source(source: str) -> Module:
    tree = _parser().parse(source)
    module = _ToAst().transform(tree)
    if getattr(module, "__circlelib_scene_count__", 0) > 1:
        raise SyntaxError("only one scene block is allowed per file")
    if getattr(module, "__circlelib_animate_count__", 0) > 1:
        raise SyntaxError("only one animate block is allowed per file")
    return module


def parse_file(path: str | Path) -> Module:
    return parse_source(Path(path).read_text(encoding="utf-8"))
