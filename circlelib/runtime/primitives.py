"""Mesh generators for built-in primitives.

Each function returns (vertices, indices, normals) as numpy float32 /
uint32 arrays in object-local space (centered at origin). The evaluator
later wraps each mesh in a SceneNode and applies a transform.
"""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np


Mesh = Tuple[np.ndarray, np.ndarray, np.ndarray]


def cube(width: float, height: float, depth: float) -> Mesh:
    hx, hy, hz = width / 2.0, height / 2.0, depth / 2.0
    # Six faces, each as two triangles. Per-face normals.
    faces = [
        # +X
        ([(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)], (1, 0, 0)),
        # -X
        ([(-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz), (-hx, -hy, -hz)], (-1, 0, 0)),
        # +Y
        ([(-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz)], (0, 1, 0)),
        # -Y
        ([(-hx, -hy, hz), (-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz)], (0, -1, 0)),
        # +Z
        ([(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)], (0, 0, 1)),
        # -Z
        ([(hx, -hy, -hz), (-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz)], (0, 0, -1)),
    ]

    verts: list[tuple[float, float, float]] = []
    norms: list[tuple[float, float, float]] = []
    indices: list[int] = []
    for quad, normal in faces:
        base = len(verts)
        for v in quad:
            verts.append(v)
            norms.append(normal)
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]

    return (
        np.array(verts, dtype="f4"),
        np.array(indices, dtype="u4"),
        np.array(norms, dtype="f4"),
    )


def sphere(radius: float, segments: int = 24, rings: int = 16) -> Mesh:
    verts: list[tuple[float, float, float]] = []
    norms: list[tuple[float, float, float]] = []
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        y = math.cos(phi)
        r = math.sin(phi)
        for seg in range(segments + 1):
            theta = 2 * math.pi * seg / segments
            x = r * math.cos(theta)
            z = r * math.sin(theta)
            verts.append((radius * x, radius * y, radius * z))
            norms.append((x, y, z))

    indices: list[int] = []
    stride = segments + 1
    for ring in range(rings):
        for seg in range(segments):
            a = ring * stride + seg
            b = a + 1
            c = a + stride
            d = c + 1
            indices += [a, c, b, b, c, d]

    return (
        np.array(verts, dtype="f4"),
        np.array(indices, dtype="u4"),
        np.array(norms, dtype="f4"),
    )


def cylinder(radius: float, height: float, segments: int = 32) -> Mesh:
    half = height / 2.0
    verts: list[tuple[float, float, float]] = []
    norms: list[tuple[float, float, float]] = []
    indices: list[int] = []

    # Side wall: two rings of vertices, normals pointing outward.
    for seg in range(segments + 1):
        theta = 2 * math.pi * seg / segments
        x = math.cos(theta)
        z = math.sin(theta)
        verts.append((radius * x, -half, radius * z))
        norms.append((x, 0.0, z))
        verts.append((radius * x, half, radius * z))
        norms.append((x, 0.0, z))

    for seg in range(segments):
        a = seg * 2
        b = a + 1
        c = a + 2
        d = a + 3
        indices += [a, c, b, b, c, d]

    # Caps (flat normals).
    bottom_center = len(verts)
    verts.append((0.0, -half, 0.0))
    norms.append((0.0, -1.0, 0.0))
    bottom_start = len(verts)
    for seg in range(segments + 1):
        theta = 2 * math.pi * seg / segments
        verts.append((radius * math.cos(theta), -half, radius * math.sin(theta)))
        norms.append((0.0, -1.0, 0.0))
    for seg in range(segments):
        indices += [bottom_center, bottom_start + seg + 1, bottom_start + seg]

    top_center = len(verts)
    verts.append((0.0, half, 0.0))
    norms.append((0.0, 1.0, 0.0))
    top_start = len(verts)
    for seg in range(segments + 1):
        theta = 2 * math.pi * seg / segments
        verts.append((radius * math.cos(theta), half, radius * math.sin(theta)))
        norms.append((0.0, 1.0, 0.0))
    for seg in range(segments):
        indices += [top_center, top_start + seg, top_start + seg + 1]

    return (
        np.array(verts, dtype="f4"),
        np.array(indices, dtype="u4"),
        np.array(norms, dtype="f4"),
    )


def torus(
    radius: float,
    tube: float,
    major_segments: int = 48,
    minor_segments: int = 16,
) -> Mesh:
    """A 3D ring (torus) lying flat on the XZ plane.

    `radius` is the distance from the centre of the torus to the centre
    of the tube. `tube` is the radius of the tube itself. Default
    `tube = radius * 0.1` gives a thin ring; larger values produce
    chunkier 3D circles.
    """
    verts: list[tuple[float, float, float]] = []
    norms: list[tuple[float, float, float]] = []
    for i in range(major_segments + 1):
        phi = 2 * math.pi * i / major_segments
        cp, sp = math.cos(phi), math.sin(phi)
        for j in range(minor_segments + 1):
            theta = 2 * math.pi * j / minor_segments
            ct, st = math.cos(theta), math.sin(theta)
            # Normal points outward from the centre of the tube.
            nx = ct * cp
            ny = st
            nz = ct * sp
            verts.append((
                (radius + tube * ct) * cp,
                tube * st,
                (radius + tube * ct) * sp,
            ))
            norms.append((nx, ny, nz))

    indices: list[int] = []
    stride = minor_segments + 1
    for i in range(major_segments):
        for j in range(minor_segments):
            a = i * stride + j
            b = a + 1
            c = a + stride
            d = c + 1
            indices += [a, b, c, b, d, c]

    return (
        np.array(verts, dtype="f4"),
        np.array(indices, dtype="u4"),
        np.array(norms, dtype="f4"),
    )
