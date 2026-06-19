from __future__ import annotations

import functools
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .path_state import PathState
from .spec import CommandSpec, LiteralSpec, PathSpec, ShellSpec


@dataclass(frozen=True, slots=True)
class CompletionResult:
    text: str
    display: str


@dataclass(frozen=True, slots=True)
class CompletionError:
    msg: str = ""


class Completer(ABC):
    @abstractmethod
    def complete(self, text: str) -> list[CompletionResult] | CompletionError: ...


@dataclass(frozen=True)
class LiteralCompleter(Completer):
    spec: LiteralSpec

    def complete(self, text: str) -> list[CompletionResult] | CompletionError:
        if not self.spec.literal.startswith(text):
            return CompletionError()
        return [CompletionResult(self.spec.literal[len(text) :], self.spec.literal)]


# BUG: Output path is completely broken.
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
