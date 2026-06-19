import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
???LINES MISSING
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
