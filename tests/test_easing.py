"""Unit tests for the easing curves used by `anim()`."""

from __future__ import annotations

import pytest

from circlelib.runtime.easing import (
    EASINGS,
    bounce,
    ease_in,
    ease_in_out,
    ease_out,
    linear,
    resolve_easing,
)


def test_all_five_tweens_are_registered():
    assert set(EASINGS) == {
        "linear", "ease_in", "ease_out", "ease_in_out", "bounce"
    }


def test_linear_is_identity():
    for p in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert linear(p) == pytest.approx(p)


def test_ease_in_starts_slow_ends_fast():
    assert ease_in(0.0) == pytest.approx(0.0)
    assert ease_in(1.0) == pytest.approx(1.0)
    # First quarter of progress travels less than a quarter of distance.
    assert ease_in(0.25) < 0.25
    # Final quarter travels more than a quarter.
    assert (ease_in(1.0) - ease_in(0.75)) > 0.25


def test_ease_out_starts_fast_ends_slow():
    assert ease_out(0.0) == pytest.approx(0.0)
    assert ease_out(1.0) == pytest.approx(1.0)
    assert ease_out(0.25) > 0.25
    assert (ease_out(1.0) - ease_out(0.75)) < 0.25


def test_ease_in_out_is_symmetric():
    # The standard (1 - cos(πp)) / 2 family is symmetric around p=0.5;
    # this implementation is the quadratic variant which is also
    # symmetric: f(p) + f(1-p) == 1 within float tolerance.
    for p in (0.1, 0.3, 0.5, 0.8):
        assert ease_in_out(p) + ease_in_out(1 - p) == pytest.approx(1.0, abs=1e-6)


def test_bounce_endpoints_and_monotonic_per_lobe():
    assert bounce(0.0) == pytest.approx(0.0)
    # Bounce's last lobe ends at 1.0 by construction.
    assert bounce(1.0) == pytest.approx(1.0, abs=1e-6)
    # Inside the first lobe (p < 1/2.75 ≈ 0.36) bounce is monotonic.
    samples = [bounce(p) for p in (0.0, 0.1, 0.2, 0.3)]
    assert samples == sorted(samples)


def test_resolve_easing_returns_callable_or_none():
    assert resolve_easing("linear") is linear
    assert resolve_easing("ease_in_out") is ease_in_out
    assert resolve_easing("nope") is None
