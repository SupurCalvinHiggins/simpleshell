import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# On keypress:
# - Consume all contents of current buffer
# - Check additional keypress is legal (custom error message?)
# On enter:
# - Consume all contents of current buffer
# - Check enter is legal (custom error messages?)
# Note: Should probably handle enter and keypress the same
# On autosuggest:
# - Consume all contents of current buffer
# - Get all completions, if only one, suggest it
# On input done:
# - Consume all contents of current buffer
# - Get contents of parsed command and execute it
# On completion request:
# - Consume all contents of current buffer
# - Get all completions

# What else might we like to do?
# - Display the set of valid next characters
# -

# What questions are there:
# - Is the set of all displayed completions the same as what we should allow to be typed?

# What does this mean:
# - get all completions
# - get parsed version (tokens/arguments)


@dataclass
class Completion:
    text: str
    display: str


class Parser(ABC):
    @abstractmethod
    def completions(self, token: str) -> list[Completion]:
        # [] means invalid
        # [""] means current is valid
        # ["", "ack/"] means current is valid or can extend with "ack/"
        ...

    @abstractmethod
    def parse(self, token: str) -> Any: ...


@dataclass
class LiteralParser(Parser):
    literal: str

    def completions(self, token: str) -> list[Completion]:
        completions = []
        if self.literal.startswith(token):
            completion = Completion(self.literal[len(token) :], self.literal)
            completions.append(completion)
        return completions

    def parse(self, token: str) -> str | None:
        return token if token == self.literal else None


@dataclass
class PathParser(Parser):
    must_exist: bool | None = None
    must_be_dir: bool | None = None
    suffix: str | None = None

    def _candidates(self, token: str) -> list[Path]:
        directory, suffix = os.path.split(token)

        # Candidates only exist if the path exists.
        path = Path(directory) if directory else Path(".")
        if not path.is_dir():
            return []

        candidates = sorted(path.iterdir())
        # .. is only a candidate if the path does not yet include a non-.. component.
        if not directory or directory.rstrip("/").endswith(".."):
            candidates = [Path(".."), *candidates]

        # Candidates must extend the suffix.
        return [path for path in candidates if path.name.startswith(suffix)]

    def completions(self, token: str) -> list[Completion]:
        directory, suffix = os.path.split(token)

        result = []

        # Check if the current token is valid.
        if token and self._is_valid(Path(token)):
            result.append(Completion("", token))

        # Check if any candidate paths are valid.
        for path in self._candidates(token):
            if not self._is_valid(path):
                continue
            name = path.name + "/" if path.is_dir() else path.name
            result.append(Completion(name[len(suffix) :], name))

        return result

    def _is_valid(self, path: Path) -> bool:
        if self.must_exist is True and not path.exists():
            return False
        if self.must_exist is False and path.exists():
            return False
        # BUG: is_dir returns False if the path does not exist.
        if self.must_be_dir is True and not path.is_dir():
            return False
        if self.must_be_dir is False and path.is_dir():
            return False
        if self.suffix and path.suffix != self.suffix:
            return False
        return True

    def parse(self, token: str) -> Path | None:
        path = Path(token)
        if not self._is_valid(path):
            return None
        return path


class InputDirParser(PathParser):
    def __init__(self) -> None:
        super().__init__(must_exist=True, must_be_dir=True)


class InputFileParser(PathParser):
    def __init__(self) -> None:
        super().__init__(must_exist=True, must_be_dir=False)


class OutputDirParser(PathParser):
    def __init__(self) -> None:
        super().__init__(must_exist=False, must_be_dir=True)


class OutputFileParser(PathParser):
    def __init__(self) -> None:
        super().__init__(must_exist=False, must_be_dir=False)


@dataclass
class CdCommand:
    path: Path


@dataclass
class LsCommand:
    path: Path = field(default_factory=lambda: Path("."))


@dataclass
class PwdCommand: ...


@dataclass
class CatCommand:
    path: Path


@dataclass
class TouchCommand:
    path: Path


@dataclass
class MkdirCommand:
    path: Path


@dataclass
class RmCommand:
    path: Path


@dataclass
class RmdirCommand:
    path: Path


@dataclass
class CpCommand:
    source_path: Path
    destination_path: Path


@dataclass
class CpRCommand:
    source_path: Path
    destination_path: Path


@dataclass
class PythonCommand:
    path: Path


Command = (
    CdCommand
    | LsCommand
    | PwdCommand
    | CatCommand
    | TouchCommand
    | MkdirCommand
    | RmdirCommand
    | CpCommand
    | CpRCommand
    | PythonCommand
)


@dataclass
class CommandParser:
    args: list[Parser]
    result: Callable[..., Command]

    def completions(self, tokens: list[str]) -> list[Completion]:
        if not tokens or len(tokens) > len(self.args):
            return []

        index = len(tokens) - 1
        for i in range(index):
            if not self.args[i].completions(tokens[i]):
                return []

        token = tokens[index]
        arg = self.args[index]
        completions = arg.completions(token)

        if not completions:
            # TODO: Compute error message here.
            return []

        result = []
        # TODO: do fusion of " " with non-empty completions
        # i think this is possible when there is only one valid completion?
        # no, even if there is only one valid completion for a path, there
        # may be more left to the path; this might only be valid for literals
        # might not be desirable: we would have both "ls" and "ls " as completions
        for completion in completions:
            # Extend complete arguments with a space.
            if completion.text == "" and index < len(self.args) - 1:
                result.append(Completion(" ", completion.display))
            else:
                result.append(completion)

        return result

    def parse(self, tokens: list[str]) -> Command | None:
        if len(tokens) != len(self.args):
            return None
        parsed = []
        for arg, token in zip(self.args, tokens):
            value = arg.parse(token)
            if value is None:
                return None
            if isinstance(arg, LiteralParser):
                continue
            parsed.append(value)
        return self.result(*parsed)


@dataclass
class ShellParser:
    commands: list[CommandParser]

    def completions(self, buffer: str) -> list[Completion]:
        tokens = buffer.split(" ")
        result = []
        seen = set()
        for cmd in self.commands:
            for c in cmd.completions(tokens):
                key = (c.text, c.display)
                if key not in seen:
                    seen.add(key)
                    result.append(c)
        return result

    def parse(self, buffer: str) -> list[Any] | None:
        tokens = buffer.split(" ")
        for cmd in self.commands:
            result = cmd.parse(tokens)
            if result is not None:
                return result
        return None


def make_parser() -> ShellParser:
    return ShellParser(
        [
            CommandParser([LiteralParser("cd"), InputDirParser()], CdCommand),
            CommandParser([LiteralParser("ls")], LsCommand),
            CommandParser([LiteralParser("ls"), InputDirParser()], LsCommand),
            CommandParser([LiteralParser("pwd")], PwdCommand),
            CommandParser([LiteralParser("cat"), InputFileParser()], CatCommand),
            CommandParser([LiteralParser("touch"), OutputFileParser()], TouchCommand),
            CommandParser([LiteralParser("mkdir"), OutputDirParser()], MkdirCommand),
            CommandParser([LiteralParser("rm"), InputFileParser()], RmCommand),
            CommandParser([LiteralParser("rmdir"), InputDirParser()], RmdirCommand),
            CommandParser(
                [LiteralParser("cp"), InputFileParser(), OutputFileParser()], CpCommand
            ),
            CommandParser(
                [
                    LiteralParser("cp"),
                    LiteralParser("-r"),
                    InputDirParser(),
                    OutputDirParser(),
                ],
                CpRCommand,
            ),
            CommandParser(
                [
                    LiteralParser("python3"),
                    PathParser(must_exist=True, must_be_dir=False, suffix=".py"),
                ],
                PythonCommand,
            ),
        ]
    )
