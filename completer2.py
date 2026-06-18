import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
class CommandParser:
    args: list[Parser]

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
        for completion in completions:
            # Extend complete arguments with a space.
            if completion.text == "" and index < len(self.args) - 1:
                result.append(Completion(" ", completion.display))
            else:
                result.append(completion)

        return result

    def parse(self, tokens: list[str]) -> list[Any] | None:
        if len(tokens) != len(self.args):
            return None
        parsed = []
        for arg, token in zip(self.args, tokens):
            value = arg.parse(token)
            if value is None:
                return None
            parsed.append(value)
        return parsed


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


if __name__ == "__main__":
    COMMANDS = ShellParser(
        [
            CommandParser([LiteralParser("cd"), InputDirParser()]),
            CommandParser([LiteralParser("ls")]),
            CommandParser([LiteralParser("ls"), InputDirParser()]),
            CommandParser([LiteralParser("pwd")]),
            CommandParser([LiteralParser("cat"), InputFileParser()]),
            CommandParser([LiteralParser("touch"), OutputFileParser()]),
            CommandParser([LiteralParser("mkdir"), OutputDirParser()]),
            CommandParser([LiteralParser("rm"), InputFileParser()]),
            CommandParser([LiteralParser("rmdir"), InputDirParser()]),
            CommandParser([LiteralParser("cp"), InputFileParser(), OutputFileParser()]),
            CommandParser(
                [
                    LiteralParser("cp"),
                    LiteralParser("-r"),
                    InputDirParser(),
                    OutputDirParser(),
                ]
            ),
            CommandParser(
                [
                    LiteralParser("python3"),
                    PathParser(must_exist=True, must_be_dir=False, suffix=".py"),
                ]
            ),
        ]
    )

    for buffer in ["l", "ls", "ls ", "ls .git/", "cp ", "cp pars"]:
        print(f"buffer={buffer!r}")
        completions = COMMANDS.completions(buffer)
        for c in completions:
            print(f"  {c}")
        print()
