from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

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


class CommandKind(Enum): ...


@dataclass
class ParseResult[T]:
    data: T


@dataclass
class CommandParseResult[T](ParseResult[T]):
    kind: CommandKind


class ParseError: ...


class Parser[T](ABC):
    @abstractmethod
    def parse(self, text: str) -> ParseResult[T] | ParseError: ...


class CommandParser[T](Parser[T]):
    @abstractmethod
    def parse(self, text: str) -> CommandParseResult[T] | ParseError: ...


@dataclass
class CompletionResult:
    text: str
    display: str


class CompletionError: ...


class Completer(ABC):
    @abstractmethod
    def complete(self, text: str) -> list[CompletionResult] | CompletionError: ...


class Executor[T](ABC):
    @abstractmethod
    def execute(self, cmd: CommandParseResult[T]) -> None: ...


class Spec[T](ABC):
    @abstractmethod
    def parser(self) -> Parser[T]: ...

    @abstractmethod
    def completer(self) -> Completer: ...


class ExecutableSpec[T](Spec[T]):
    @abstractmethod
    def parser(self) -> CommandParser[T]: ...

    @abstractmethod
    def executor(self) -> Executor[T]: ...


@dataclass(frozen=True)
class LiteralParser(Parser[str]):
    literal: str

    def parse(self, text: str) -> ParseResult[str] | ParseError:
        if text != self.literal:
            return ParseError()
        return ParseResult(text)


@dataclass(frozen=True)
class LiteralCompleter(Completer):
    literal: str

    def complete(self, text: str) -> list[CompletionResult] | CompletionError:
        if not self.literal.startswith(text):
            return CompletionError()
        return [CompletionResult(self.literal[len(text) :], self.literal)]


@dataclass(frozen=True)
class LiteralSpec(Spec[str]):
    literal: str

    def parser(self) -> Parser[str]:
        return LiteralParser(self.literal)

    def completer(self) -> Completer:
        return LiteralCompleter(self.literal)


# dne, exists and file, exists and dir, dont care


class PathState(Enum):
    DNE = auto()
    FILE = auto()
    DIR = auto()


@dataclass(frozen=True)
class PathParser(Parser[Path]):
    state: PathState | None = None
    suffix: str | None = None

    def parse(self, text: str) -> ParseResult[Path] | ParseError:
        # TODO:
        raise NotImplementedError


@dataclass(frozen=True)
class PathCompleter(Completer):
    state: PathState | None = None
    suffix: str | None = None

    def complete(self, text: str) -> list[CompletionResult] | CompletionError:
        # TODO:
        raise NotImplementedError


@dataclass(frozen=True)
class PathSpec(Spec[Path]):
    state: PathState | None = None
    suffix: str | None = None

    def parser(self) -> PathParser:
        return PathParser(self.state, self.suffix)

    def completer(self) -> PathCompleter:
        return PathCompleter(self.state, self.suffix)


class InputDirSpec(PathSpec):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs, state=PathState.DIR)


class InputFileSpec(PathSpec):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs, state=PathState.FILE)


class OutputPathSpec(PathSpec):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs, state=PathState.DNE)


@dataclass(frozen=True)
class CommandParser(Parser[list[str | Path]]): ...


@dataclass(frozen=True)
class CommandCompleter(Completer): ...


@dataclass(frozen=True)
class CommandSpec(Spec[list[str | Path]]):
    specs: list[LiteralSpec | PathSpec]

    def parser(self) -> CommandParser:
        # TODO:
        raise NotImplementedError

    def completer(self) -> CommandCompleter:
        # TODO:
        raise NotImplementedError


@dataclass(frozen=True)
class ShellSpec(Spec[list[str | Path]]):
    specs: list[CommandSpec]

    def parser(self) -> ShellParser:
        # TODO:
        raise NotImplementedError

    def completer(self) -> ShellCompleter:
        # TODO:
        raise NotImplementedError


# Architecture:
# Define available commands with a Spec
# Specs know how to convert themselves to (1) parsers, (2) completers and (3) executors
# Build parser and completer
# Drive input with completer, parse final result with parser (returns )

# Spec -> Completer -> text
# v
# Parser + text -> (CommandKind, list[arg])
# Executor + (CommandKind, list[arg]) -> side effect
