from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .path_state import PathState
from .spec import (
    CommandCallback,
    CommandData,
    CommandSpec,
    LiteralSpec,
    PathSpec,
    ShellSpec,
)


@dataclass(frozen=True, slots=True)
class ParseResult[T]:
    data: T


@dataclass(frozen=True, slots=True)
class CommandParseResult(ParseResult[CommandData]):
    callback: CommandCallback


@dataclass(frozen=True, slots=True)
class ParseError:
    msg: str = ""
    position: int = 0


class Parser[T](ABC):
    @abstractmethod
    def parse(self, text: str) -> ParseResult[T] | ParseError: ...


@dataclass(frozen=True)
class LiteralParser(Parser[str]):
    spec: LiteralSpec

    def parse(self, text: str) -> ParseResult[str] | ParseError:
        if text != self.spec.literal:
            return ParseError(f"expected {self.spec.literal} but found {text}")
        return ParseResult(text)


@dataclass(frozen=True)
class PathParser(Parser[Path]):
    spec: PathSpec

    def parse(self, text: str) -> ParseResult[Path] | ParseError:
        if not text:
            return ParseError("expected a path but found nothing")

        path = Path(text)
        if self.spec.state is not None:
            states = PathState.to_states(path)
            if self.spec.state not in states:
                goals = {
                    PathState.EXISTS: "exist",
                    PathState.FILE: "be a file",
                    PathState.DIR: "be a directory",
                    PathState.DNE: "not exist",
                }
                reasons = {
                    PathState.EXISTS: "it does not exist",
                    PathState.FILE: "it does not exist"
                    if not path.exists()
                    else "it was a directory",
                    PathState.DIR: "it does not exist"
                    if not path.exists()
                    else "it was a file",
                    PathState.DNE: "it exists",
                }
                return ParseError(
                    f"expected {text} to {goals[self.spec.state]} but {reasons[self.spec.state]}"
                )

        return ParseResult(path)


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
        data = []
        for i, (part, parser) in enumerate(zip(parts, self._parsers)):
            result = parser.parse(part)
            if isinstance(result, ParseError):
                return ParseError(result.msg, position=i)
            data.append(result.data)
        # this must be checked afterwards, otherwise, we report a stronger error than needed
        if len(parts) != len(self._parsers):
            return ParseError(
                f"{len(parts)} arguments provided but {len(self._parsers)} arguments expected",
                position=min(len(parts), len(self._parsers)),
            )
        return CommandParseResult(data, self.spec.callback)


@dataclass(frozen=True)
class ShellParser(CommandParser):
    spec: ShellSpec

    @functools.cached_property
    def _parsers(self) -> list[CommandParser]:
        return [CommandParser(spec) for spec in self.spec.specs]

    def parse(self, text: str) -> CommandParseResult | ParseError:
        error = ParseError()
        for parser in self._parsers:
            result = parser.parse(text)
            if isinstance(result, CommandParseResult):
                return result

            if result.position > error.position:
                error = result

        return error
