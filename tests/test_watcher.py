"""Tests for the live-reload `FileWatcher` core (no GLFW involved).

Exercises mtime-tracking behaviour in isolation so the integration
loop in ``window.py`` only needs to call ``changed()`` / ``retarget()``
correctly.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from circlelib.runtime.watcher import FileWatcher


def _touch(path: Path, content: str = "x") -> None:
    """Write content and bump the mtime by 1 s.

    The +1 s offset makes the test robust to filesystems whose mtime
    resolution is 1 second (older HFS+ on macOS, certain network FS).
    """
    path.write_text(content)
    new_mtime = path.stat().st_mtime + 1.0
    os.utime(path, (new_mtime, new_mtime))


def test_fresh_watcher_reports_no_change(tmp_path):
    f = tmp_path / "a.crl"
    f.write_text("x")
    w = FileWatcher([f])
    assert w.changed() is False


def test_watcher_detects_modification(tmp_path):
    f = tmp_path / "a.crl"
    f.write_text("x")
    w = FileWatcher([f])
    _touch(f, "y")
    assert w.changed() is True


def test_change_event_consumed_after_first_observation(tmp_path):
    f = tmp_path / "a.crl"
    f.write_text("x")
    w = FileWatcher([f])
    _touch(f, "y")
    assert w.changed() is True
    # Subsequent calls without a new write report False.
    assert w.changed() is False


def test_watcher_handles_multiple_files(tmp_path):
    a = tmp_path / "a.crl"
    b = tmp_path / "b.crl"
    a.write_text("a")
    b.write_text("b")
    w = FileWatcher([a, b])
    _touch(b, "b2")
    assert w.changed() is True
    assert w.changed() is False


def test_simultaneous_save_reports_one_event(tmp_path):
    """Editing two files in one save should still produce one event,
    not one per file. The watcher refreshes the snapshot in one pass."""
    a = tmp_path / "a.crl"
    b = tmp_path / "b.crl"
    a.write_text("a")
    b.write_text("b")
    w = FileWatcher([a, b])
    _touch(a, "a2")
    _touch(b, "b2")
    assert w.changed() is True
    assert w.changed() is False


def test_retarget_replaces_tracked_set(tmp_path):
    a = tmp_path / "a.crl"
    b = tmp_path / "b.crl"
    a.write_text("a")
    b.write_text("b")
    w = FileWatcher([a])
    # `b` is not tracked yet, so editing it does nothing.
    _touch(b, "b2")
    assert w.changed() is False

    w.retarget([a, b])
    _touch(b, "b3")
    assert w.changed() is True


def test_missing_file_does_not_crash(tmp_path):
    f = tmp_path / "ghost.crl"
    f.write_text("x")
    w = FileWatcher([f])
    f.unlink()
    # A vanished file is treated as "no signal"; the watcher does not
    # raise. The next time the file reappears, that's reported as a
    # change.
    assert w.changed() is False
    f.write_text("again")
    new_mtime = time.time() + 5
    os.utime(f, (new_mtime, new_mtime))
    assert w.changed() is True
