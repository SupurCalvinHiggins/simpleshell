from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from path_state import PathState
from spec import (
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


class ParseError: ...


class Parser[T](ABC):
    @abstractmethod
    def parse(self, text: str) -> ParseResult[T] | ParseError: ...


@dataclass(frozen=True)
class LiteralParser(Parser[str]):
    spec: LiteralSpec

    def parse(self, text: str) -> ParseResult[str] | ParseError:
        if text != self.spec.literal:
            return ParseError()
        return ParseResult(text)


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
        data = []
        for part, parser in zip(parts, self._parsers):
            result = parser.parse(part)
            if isinstance(result, ParseError):
                return result
            data.append(result.data)
        return CommandParseResult(data, self.spec.callback)


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
