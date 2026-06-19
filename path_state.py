from __future__ import annotations

from enum import Enum, auto
from pathlib import Path


class PathState(Enum):
    # NOTE: When should we verify parent path exists?
    DNE = auto()
    EXISTS = auto()
    FILE = auto()
    DIR = auto()

    @staticmethod
    def to_states(path: Path) -> list[PathState]:
        states = []
        if path.exists():
            states.append(PathState.EXISTS)
            states.append(PathState.DIR if path.is_dir() else PathState.FILE)
        else:
            states.append(PathState.DNE)
        return states
