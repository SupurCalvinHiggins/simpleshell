from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Self

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


@dataclass
class ParseResult[T]:
    data: T


CommandData = list[str | Path]
CommandCallback = Callable[[CommandData], None]


@dataclass
class CommandParseResult(ParseResult[CommandData]):
    callback: CommandCallback


class ParseError: ...


class Parser[T](ABC):
    @abstractmethod
    def parse(self, text: str) -> ParseResult[T] | ParseError: ...

    @abstractmethod
    @classmethod
    def from_spec(spec: Spec) -> Self: ...


@dataclass
class CompletionResult:
    text: str
    display: str


class CompletionError: ...


class Completer(ABC):
    @abstractmethod
    def complete(self, text: str) -> list[CompletionResult] | CompletionError: ...


class Executor(ABC):
    @abstractmethod
    def execute(self, cmd: CommandParseResult) -> None: ...


class Spec[T](ABC):
    @abstractmethod
    def parser(self) -> Parser[T]: ...

    @abstractmethod
    def completer(self) -> Completer: ...


ExecutableSpec = Spec[CommandData]


@dataclass(frozen=True)
class LiteralParser(Parser[str]):
    spec: LiteralSpec

    def parse(self, text: str) -> ParseResult[str] | ParseError:
        if text != self.literal:
            return ParseError()
        return ParseResult(text)


@dataclass(frozen=True)
class LiteralCompleter(Completer):
    spec: LiteralSpec

    def complete(self, text: str) -> list[CompletionResult] | CompletionError:
        if not self.spec.literal.startswith(text):
            return CompletionError()
        return [CompletionResult(self.spec.literal[len(text) :], self.spec.literal)]


@dataclass(frozen=True)
class LiteralSpec(Spec[str]):
    literal: str

    def parser(self) -> Parser[str]:
        return LiteralParser(self)

    def completer(self) -> Completer:
        return LiteralCompleter(self)


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


@dataclass(frozen=True)
class PathParser(Parser[Path]):
    spec: PathSpec

    def parse(self, text: str) -> ParseResult[Path] | ParseError:
        if not text:
            return ParseError()

        path = Path(text)
        if self.spec.state is not None:
            states = PathState.to_states(path)
            if self.spec.state not in states:
                return ParseError()

        return ParseResult(path)


@dataclass(frozen=True)
class PathCompleter(Completer):
    spec: PathSpec

    def _candidates(self, directory: str, suffix: str) -> list[Path]:
        # Candidates only exist if the path exists.
        path = Path(directory or ".")
        if not path.is_dir():
            return []

        # TODO: Add . as a candidate when reasonable.
        candidates = list(path.iterdir())

        # .. is only a candidate if the path does not yet include a non-.. component.
        if not directory or directory.rstrip("/").endswith(".."):
            candidates.append(Path(".."))

        # Candidates must extend the suffix
        candidates = [path for path in candidates if path.name.startswith(suffix)]

        # The current directory is a candidate if there is no suffix.
        if directory and not suffix:
            candidates.append(Path(""))

        candidates.sort()

        return candidates

    def complete(self, text: str) -> list[CompletionResult] | CompletionError:
        directory, suffix = os.path.split(text)

        completions = []

        # Check if any candidate paths are valid.
        for path in self._candidates(directory, suffix):
            states = PathState.to_states(path)
            if self.spec.state not in states:
                continue
            name = path.name + "/" if path.is_dir() and path != Path("") else path.name
            completions.append(CompletionResult(name[len(suffix) :], name))

        if not completions:
            return CompletionError()

        return completions


@dataclass(frozen=True)
class PathSpec(Spec[Path]):
    state: PathState | None = None
    suffix: str | None = None

    def parser(self) -> PathParser:
        return PathParser(self)

    def completer(self) -> PathCompleter:
        return PathCompleter(self)


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


@dataclass(frozen=True)
class CommandParser(Parser[CommandData]):
    def parse(self, text: str) -> CommandParseResult:
        parts = text.split(" ")
        return [self.spec()]

        raise NotImplementedError


@dataclass(frozen=True)
class CommandCompleter(Completer): ...


@dataclass(frozen=True)
class CommandSpec(ExecutableSpec):
    specs: list[LiteralSpec | PathSpec]

    @staticmethod
    def _default_callback(args: CommandData) -> None:
        raise NotImplementedError

    callback: CommandCallback = _default_callback

    def parser(self) -> CommandParser:
        # TODO:
        raise NotImplementedError

    def completer(self) -> CommandCompleter:
        # TODO:
        raise NotImplementedError


@dataclass(frozen=True)
class ShellParser(CommandParser):
    def parse(self, text: str) -> CommandParseResult:
        raise NotImplementedError


@dataclass(frozen=True)
class ShellCompleter(Completer): ...


@dataclass(frozen=True)
class ShellSpec(ExecutableSpec):
    specs: list[CommandSpec]

    def parser(self) -> ShellParser:
        # TODO:
        raise NotImplementedError

    def completer(self) -> ShellCompleter:
        # TODO:
        raise NotImplementedError


if __name__ == "__main__":
    for text in ["", ".", "..", "../"]:
        print(text)
        print(PathCompleter(PathState.EXISTS).complete(text))

    spec = ShellSpec(
        [
            CommandSpec([LiteralSpec("cd"), InputDirSpec()]),
            CommandSpec([LiteralSpec("ls")]),
            CommandSpec([LiteralSpec("ls"), InputDirSpec()]),
            CommandSpec([LiteralSpec("pwd")]),
            CommandSpec([LiteralSpec("cat"), InputFileSpec()]),
            CommandSpec([LiteralSpec("touch"), OutputPathSpec()]),
            CommandSpec([LiteralSpec("mkdir"), OutputPathSpec()]),
            CommandSpec([LiteralSpec("rm"), InputFileSpec()]),
            CommandSpec([LiteralSpec("rm"), LiteralSpec("-r"), InputDirSpec()]),
            CommandSpec([LiteralSpec("rmdir"), InputDirSpec()]),
            CommandSpec([LiteralSpec("mv"), InputPathSpec(), OutputPathSpec()]),
            CommandSpec([LiteralSpec("cp"), InputFileSpec(), OutputPathSpec()]),
            CommandSpec(
                [LiteralSpec("cp"), LiteralSpec("-r"), InputDirSpec(), OutputPathSpec()]
            ),
            CommandSpec([LiteralSpec("python3"), InputFileSpec(suffix=".py")]),
        ]
    )

# Architecture:
# Define available commands with a Spec
# Specs know how to convert themselves to (1) parsers, (2) completers and (3) executors
# Build parser and completer
# Drive input with completer, parse final result with parser (returns )

# Spec -> Completer -> text
# v
# Parser + text -> (CommandKind, list[arg])
# Executor + (CommandKind, list[arg]) -> side effect
