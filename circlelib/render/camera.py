"""Orbit camera that yaws/pitches around the origin.

The camera is described by spherical coordinates (radius, yaw, pitch)
around the world origin. Mouse drag rotates; scroll zooms.
"""

from __future__ import annotations

import math

import numpy as np
from pyrr import Matrix44


class OrbitCamera:
    def __init__(
        self,
        *,
        radius: float = 18.0,
        yaw: float = math.radians(35.0),
        pitch: float = math.radians(25.0),
        target=(0.0, 0.0, 0.0),
        fov_degrees: float = 60.0,
        near: float = 0.1,
        far: float = 1000.0,
    ) -> None:
        self.radius = radius
        self.yaw = yaw
        self.pitch = pitch
        self.target = np.array(target, dtype="f4")
        self.fov = math.radians(fov_degrees)
        self.near = near
        self.far = far

    def rotate(self, dx: float, dy: float) -> None:
        self.yaw += dx * 0.005
        self.pitch += dy * 0.005
        # Clamp pitch so we never hit the poles.
        limit = math.radians(89.0)
        self.pitch = max(-limit, min(limit, self.pitch))

    def zoom(self, delta: float) -> None:
        self.radius *= 1.0 - delta * 0.1
        self.radius = max(1.0, min(500.0, self.radius))

    def eye(self) -> np.ndarray:
        cp = math.cos(self.pitch)
        x = self.radius * cp * math.sin(self.yaw)
        y = self.radius * math.sin(self.pitch)
        z = self.radius * cp * math.cos(self.yaw)
        return np.array([x, y, z], dtype="f4") + self.target

    def view_matrix(self) -> np.ndarray:
        return np.array(
            Matrix44.look_at(self.eye(), self.target, (0.0, 1.0, 0.0), dtype="f4"),
            dtype="f4",
        )

    def projection_matrix(self, aspect: float) -> np.ndarray:
        return np.array(
            Matrix44.perspective_projection(
                math.degrees(self.fov), aspect, self.near, self.far, dtype="f4"
            ),
            dtype="f4",
        )
