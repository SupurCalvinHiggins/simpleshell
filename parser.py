from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Iterator


class Trit(Enum):
    YES = auto()
    NO = auto()
    MAYBE = auto()

    def __bool__(self) -> bool:
        raise TypeError("`Trit` does not support implicit conversion to bool")


class Parser(ABC):
    @abstractmethod
    def consume(self, c: str) -> None: ...

    @property
    @abstractmethod
    def lookahead(self) -> set[str]: ...

    @property
    @abstractmethod
    def status(self) -> Trit: ...


@dataclass
class LiteralParser(Parser):
    literal: str

    _i: int = 0
    _status: Trit = Trit.MAYBE

    def consume(self, c: str) -> None:
        if self._status != Trit.MAYBE:
            self._status = Trit.NO
            return

        if self.literal[self._i] != c:
            self._status = Trit.NO
            return

        self._i += 1
        if self._i == len(self.literal):
            self._status = Trit.YES

    @property
    def lookahead(self) -> set[str]:
        chars = set()

        if self._status != Trit.MAYBE:
            return chars

        chars.add(self.literal[self._i])
        return chars

    @property
    def status(self) -> Trit:
        return self._status


@dataclass
class PathParser(Parser):
    exists: Trit = Trit.MAYBE
    is_dir: Trit = Trit.MAYBE
    suffix: str | None = None

    _directory: str = ""
    _prefix: str = ""
    _status: Trit = Trit.MAYBE

    def consume(self, c: str) -> None:
        assert self.exists == Trit.YES

        if self._status == Trit.NO:
            return

        if c not in self.lookahead:
            self._status = Trit.NO
            return

        if c != "/":
            self._prefix += c
        else:
            self._directory += self._prefix + c
            self._prefix = ""

        if Path(self._directory + self._prefix).exists():
            self._status = Trit.YES
        else:
            self._status = Trit.MAYBE if self.lookahead else Trit.NO

    @property
    def completions(self) -> Iterator[str]:
        assert self.exists == Trit.YES

        # Only allow a sequence of zero or more .. at the start of the path.
        candidates = list(Path(self._directory).iterdir())
        if not self._directory or self._directory.endswith(".."):
            candidates.append(Path(".."))
        candidates.sort()

        for path in candidates:
            is_dir = path.is_dir()
            if (
                self.is_dir == Trit.YES
                and not is_dir
                or self.is_dir == Trit.NO
                and is_dir
            ):
                continue

            name = path.name + "/" if is_dir else path.name
            if not name.startswith(self._prefix):
                continue

            completion = name[len(self._prefix) :]
            yield completion

    @property
    def lookahead(self) -> set[str]:
        res = set(c[0] for c in self.completions if c)
        return res

    @property
    def status(self) -> Trit:
        return self._status


class InputDirParser(PathParser):
    def __init__(self) -> None:
        super().__init__(exists=Trit.YES, is_dir=Trit.YES)


class InputFileParser(PathParser):
    def __init__(self) -> None:
        super().__init__(exists=Trit.YES, is_dir=Trit.NO)


class OutputDirParser(PathParser):
    def __init__(self) -> None:
        super().__init__(exists=Trit.NO, is_dir=Trit.YES)


class OutputFileParser(PathParser):
    def __init__(self) -> None:
        super().__init__(exists=Trit.NO, is_dir=Trit.NO)


# required vs. optional
# specific path kinds (exists / dne, filetype, directory)
# command name

# cd, ls, touch, mkdir, rm, rmdir, mv, cat, python3, g++, pwd


"""
COMMANDS = [
    [LiteralParser("cd"), InputDirParser()],
    [LiteralParser("ls")],
    [LiteralParser("ls"), InputDirParser()],
    [LiteralParser("pwd")],
    [LiteralParser("cat"), InputFileParser()],
    [LiteralParser("touch"), OutputFileParser()],
    [LiteralParser("mkdir"), OutputDirParser()],
    [LiteralParser("rm"), InputFileParser()],
    [LiteralParser("rmdir"), InputDirParser()],
    [LiteralParser("mv"), PathParser(exists=True), PathParser(exists=False)],
    [LiteralParser("cp"), InputFileParser(), OutputFileParser()],
    [LiteralParser("cp"), LiteralParser("-r"), InputDirParser(), OutputDirParser()],
    [LiteralParser("python3"), PathParser(exists=True, is_dir=False, suffix=".py")],
]
          """


# Idea:
# Incrementally match input against set of commands. Maintain the commands with valid
# continuations. If a character is not a valid continuation of any command, reject it.
# Should the arguments be responsible for matching themselves? probably. what should that
# interface look like? well, it will take a single character and consume it. the caller
# is responsible for ensuring that the character is valid to pass
# need set of valid next characters to check this
@dataclass
class CommandParser(Parser):
    args: list[Parser]

    _i: int = 0
    _status: Trit = Trit.MAYBE

    def consume(self, c: str) -> None:
        if self._status == Trit.NO:
            return

        if c not in self.lookahead:
            self._status = Trit.NO
            return

        if c == " ":
            self._i += 1
        else:
            self.args[self._i].consume(c)

        arg = self.args[self._i]
        if self._i == len(self.args) - 1:
            self._status = arg.status

    @property
    def lookahead(self) -> set[str]:
        chars = set()

        if self._status == Trit.NO:
            return chars

        # if the current arg is good, space is valid (or \n for last arg)
        arg = self.args[self._i]
        if arg.status == Trit.YES and self._i < len(self.args) - 1:
            chars.add(" ")

        chars |= arg.lookahead
        return chars

    @property
    def status(self) -> Trit:
        return self._status


if __name__ == "__main__":
    # parser = CommandParser([LiteralParser("ls"), LiteralParser("-la")])
    parser = CommandParser([LiteralParser("ls"), InputDirParser()])
    # for c in "ls -la h":
    for c in "ls .git/z":
        print(parser.status)
        print(parser.lookahead)
        parser.consume(c)
        print(parser.status)
        print(parser.lookahead)
        print()
