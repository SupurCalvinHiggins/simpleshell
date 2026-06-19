from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from path_state import PathState

# On x press with buffer == "c":
# cx is not the start of a valid command. Press <TAB> to see all commands starting with c.
# On <ENTER> with buffer == "c":
# c is not a valid command. Press <TAB> to see all commands starting with c.
# ...

# Errors:
# - invalid command completion
# - invalid path completion
# - invalid flag completion
# - missing arguments (must know KIND of missing arg)
# - file dne but must exist (cannot occur in restricted mode)
# TDLR; some errors will come from parser, others from completer

CommandData = list[str | Path]
CommandCallback = Callable[[CommandData], None]


@dataclass(frozen=True)
class LiteralSpec:
    literal: str


@dataclass(frozen=True)
class PathSpec:
    state: PathState | None = None
    suffix: str | None = None


class OutputPathSpec(PathSpec):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs, state=PathState.DNE)


class InputPathSpec(PathSpec):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs, state=PathState.EXISTS)


class InputDirSpec(PathSpec):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs, state=PathState.DIR)


class InputFileSpec(PathSpec):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs, state=PathState.FILE)


# TODO: spec_to_parser, spec_to_completer


@dataclass(frozen=True)
class CommandSpec:
    specs: list[LiteralSpec | PathSpec]

    @staticmethod
    def _default_callback(args: CommandData) -> None:
        return None
        # raise NotImplementedError

    callback: CommandCallback = _default_callback


@dataclass(frozen=True)
class ShellSpec:
    specs: list[CommandSpec]
