import os
from pathlib import Path

from engine import (
    CommandData,
    CommandSpec,
    InputDirSpec,
    InputFileSpec,
    InputPathSpec,
    LiteralSpec,
    OutputPathSpec,
    ParseError,
    ShellCompleter,
    ShellParser,
    ShellSpec,
)


def cd(args: CommandData) -> None:
    _, dir = args
    os.chdir(dir)


def ls(args: CommandData) -> None:
    dir = Path(".") if len(args) == 1 else args[1]
    for path in dir.iterdir():
        print(path.relative_to(dir).as_posix())


def make_shell() -> tuple[ShellParser, ShellCompleter]:
    spec = ShellSpec(
        [
            CommandSpec([LiteralSpec("cd"), InputDirSpec()], callback=cd),
            CommandSpec([LiteralSpec("ls")], callback=ls),
            CommandSpec([LiteralSpec("ls"), InputDirSpec()], callback=ls),
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

    parser = ShellParser(spec)
    completer = ShellCompleter(spec)

    return parser, completer
