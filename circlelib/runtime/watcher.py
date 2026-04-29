"""Tiny mtime-polling watcher for live-reload mode.

Used by ``circlelib run --watch`` to notice when any of the user's
loaded ``.crl`` files (entry + transitive imports) is saved on disk
and trigger a reload.

The watcher is intentionally a pure-Python polling loop — no
``watchdog`` dependency, no kernel events. Polls run from the same
thread as the GL render loop; the per-tick cost is one ``stat()`` per
tracked file plus a comparison.

Public surface:

- ``FileWatcher(paths)`` — snapshot mtimes for the given paths.
- ``watcher.changed()`` — return ``True`` and update the snapshot the
  first time any tracked file's mtime moves; ``False`` otherwise. A
  freshly constructed watcher reports no change.
- ``watcher.retarget(paths)`` — replace the tracked set after a reload
  picks up a new module list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable


def _stat_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        # Treat a vanished file as "no signal" rather than a fatal
        # error — the user may be mid-rename. The next successful poll
        # picks the file up again.
        return -1.0


@dataclass
class FileWatcher:
    paths: Iterable[Path]
    _mtimes: Dict[Path, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._mtimes = {Path(p).resolve(): _stat_mtime(Path(p)) for p in self.paths}

    def changed(self) -> bool:
        for path, prev in self._mtimes.items():
            now = _stat_mtime(path)
            if now != prev and now >= 0:
                # Refresh the entire snapshot in one pass so we don't
                # report multiple events when several files were
                # written in the same save (e.g. a multi-file edit).
                self._mtimes = {p: _stat_mtime(p) for p in self._mtimes}
                return True
        return False

    def retarget(self, paths: Iterable[Path]) -> None:
        self._mtimes = {Path(p).resolve(): _stat_mtime(Path(p)) for p in paths}

    def tracked(self) -> Iterable[Path]:
        return list(self._mtimes.keys())
