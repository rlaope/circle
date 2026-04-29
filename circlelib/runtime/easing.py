"""Easing functions used by the `anim()` runtime call.

Each function maps a normalized progress in `[0, 1]` to an eased
progress (typically also in `[0, 1]`, though `bounce` may briefly
exceed for the small overshoot at the end of each lobe). They are
the standard Robert Penner curves widely used by motion-graphics
libraries.
"""

from __future__ import annotations

from typing import Callable, Optional


def linear(p: float) -> float:
    return p


def ease_in(p: float) -> float:
    return p * p


def ease_out(p: float) -> float:
    return 1.0 - (1.0 - p) ** 2


def ease_in_out(p: float) -> float:
    if p < 0.5:
        return 2.0 * p * p
    return 1.0 - (-2.0 * p + 2.0) ** 2 / 2.0


def bounce(p: float) -> float:
    n1 = 7.5625
    d1 = 2.75
    if p < 1.0 / d1:
        return n1 * p * p
    if p < 2.0 / d1:
        p = p - 1.5 / d1
        return n1 * p * p + 0.75
    if p < 2.5 / d1:
        p = p - 2.25 / d1
        return n1 * p * p + 0.9375
    p = p - 2.625 / d1
    return n1 * p * p + 0.984375


EASINGS: dict[str, Callable[[float], float]] = {
    "linear": linear,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "bounce": bounce,
}


def resolve_easing(name: str) -> Optional[Callable[[float], float]]:
    return EASINGS.get(name)
