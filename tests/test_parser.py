"""Parser unit tests."""

from circlelib.ast.nodes import (
    Argument,
    Assignment,
    Call,
    ColorLit,
    Component,
    GroupBlock,
    Identifier,
    Import,
    MemberAccess,
    NumberLit,
    Scene,
    StringLit,
    TupleLit,
)
from circlelib.parser import parse_source


def test_empty_source_is_empty_module():
    mod = parse_source("")
    assert mod.imports == []
    assert mod.components == []
    assert mod.scene is None


def test_simple_scene_with_one_call():
    src = """
    scene {
        Sphere(radius=2, position=(0, 0, 0))
    }
    """
    mod = parse_source(src)
    assert mod.scene is not None
    assert len(mod.scene.body) == 1
    call = mod.scene.body[0]
    assert isinstance(call, Call)
    assert isinstance(call.callee, Identifier)
    assert call.callee.name == "Sphere"
    assert call.args[0] == Argument("radius", NumberLit(2.0))
    assert call.args[1].name == "position"
    assert isinstance(call.args[1].value, TupleLit)
    assert [n.value for n in call.args[1].value.items] == [0.0, 0.0, 0.0]


def test_color_literal():
    mod = parse_source("scene { Sphere(radius=1, color=#ff5577) }")
    sphere = mod.scene.body[0]
    color = sphere.args[1].value
    assert isinstance(color, ColorLit)
    assert color.rgb == (255 / 255.0, 0x55 / 255.0, 0x77 / 255.0)


def test_import_and_member_access():
    src = """
    import "modules/wheels" as wheels

    scene {
        wheels.Pair(offset=(0, 0, 0))
    }
    """
    mod = parse_source(src)
    assert mod.imports == [Import(path="modules/wheels", alias="wheels")]
    call = mod.scene.body[0]
    assert isinstance(call.callee, MemberAccess)
    assert call.callee.parts == ("wheels", "Pair")


def test_component_with_assignments_and_group():
    src = """
    component Car {
        body = Cube(width=10, height=3, depth=5)
        Group(position=(0, 1, 0)) {
            Sphere(radius=1)
        }
    }
    """
    mod = parse_source(src)
    assert len(mod.components) == 1
    car = mod.components[0]
    assert car.name == "Car"
    assert isinstance(car.body[0], Assignment)
    assert car.body[0].name == "body"
    assert isinstance(car.body[0].value, Call)
    assert isinstance(car.body[1], GroupBlock)
    assert car.body[1].args[0].name == "position"
    assert len(car.body[1].body) == 1


def test_string_literal():
    mod = parse_source('scene { Cube(width=1, height=1, depth=1, label="hi") }')
    label = mod.scene.body[0].args[3].value
    assert isinstance(label, StringLit)
    assert label.value == "hi"


def test_only_one_scene_allowed():
    src = "scene { } scene { }"
    try:
        parse_source(src)
    except SyntaxError as exc:
        assert "one scene block" in str(exc)
        return
    raise AssertionError("expected SyntaxError")
