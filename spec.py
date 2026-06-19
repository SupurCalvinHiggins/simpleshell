from __future__ import annotations

import functools
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
class LiteralSpec:
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


@dataclass(frozen=True)
class CommandParser(Parser[CommandData]):
    spec: CommandSpec

    @functools.cached_property
    def _parsers(self) -> list[LiteralParser | PathParser]:
        parsers = []
        for spec in self.spec.specs:
            if isinstance(spec, LiteralSpec):
                parsers.append(LiteralParser(spec))
            elif isinstance(spec, PathSpec):
                parsers.append(PathParser(spec))
        return parsers

    def parse(self, text: str) -> CommandParseResult | ParseError:
        parts = text.split(" ")
        if len(parts) != len(self._parsers):
            return ParseError()
        data = [parser.parse(part) for part, parser in zip(parts, self._parsers)]
        return CommandParseResult(data, self.spec.callback)


# TODO: spec_to_parser, spec_to_completer


@dataclass(frozen=True)
class CommandCompleter(Completer):
    spec: CommandSpec

    @functools.cached_property
    def _completers(self) -> list[LiteralCompleter | PathCompleter]:
        completers = []
        for spec in self.spec.specs:
            if isinstance(spec, LiteralSpec):
                completers.append(LiteralCompleter(spec))
            elif isinstance(spec, PathSpec):
                completers.append(PathCompleter(spec))
        return completers

    def complete(self, text: str) -> list[CompletionResult] | CompletionError:
        parts = text.split(" ")
        if not parts or len(parts) > len(self._completers):
            return []

        index = len(parts) - 1
        for i in range(index):
            part = parts[i]
            completer = self._completers[i]
            result = completer.complete(part)
            if isinstance(result, CompletionError):
                return result

        part = parts[index]
        completer = self._completers[index]
        result = completer.complete(part)

        if isinstance(result, CompletionError):
            return result

        completions = result

        result = []
        # TODO: do fusion of " " with non-empty completions
        # i think this is possible when there is only one valid completion?
        # no, even if there is only one valid completion for a path, there
        # may be more left to the path; this might only be valid for literals
        # might not be desirable: we would have both "ls" and "ls " as completions
        for completion in completions:
            # Extend complete arguments with a space.
            if completion.text == "" and index < len(self._completers) - 1:
                result.append(CompletionResult(" ", completion.display))
            else:
                result.append(completion)

        if not result:
            return CompletionError()

        return result


@dataclass(frozen=True)
class CommandSpec:
    specs: list[LiteralSpec | PathSpec]

    @staticmethod
    def _default_callback(args: CommandData) -> None:
        raise NotImplementedError

    callback: CommandCallback = _default_callback


@dataclass(frozen=True)
class ShellParser(CommandParser):
    spec: ShellSpec

    @functools.cached_property
    def _parsers(self) -> list[CommandParser]:
        return [CommandParser(spec) for spec in self.spec.specs]

    def parse(self, text: str) -> CommandParseResult | ParseError:
        for parser in self._parsers:
            result = parser.parse(text)
            if isinstance(result, CommandParseResult):
                return result
        return ParseError()


@dataclass(frozen=True)
class ShellCompleter(Completer):
    spec: ShellSpec

    @functools.cached_property
    def _completers(self) -> list[CommandCompleter]:
        return [CommandCompleter(spec) for spec in self.spec.specs]

    def complete(self, text: str) -> list[CompletionResult] | CompletionError:
        result = []
        for completer in self._completers:
            completions = completer.complete(text)
            if isinstance(completions, CompletionError):
                continue
            result.extend(completions)
        return result


@dataclass(frozen=True)
class ShellSpec:
    specs: list[CommandSpec]


if __name__ == "__main__":
    for text in ["", ".", "..", "../"]:
        print(text)
        print(PathCompleter(InputPathSpec()).complete(text))

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
