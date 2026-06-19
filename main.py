import os
from pathlib import Path
from typing import Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
)
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_completions
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from spec import (
    CommandData,
    CommandSpec,
    InputDirSpec,
    InputFileSpec,
    InputPathSpec,
    LiteralSpec,
    OutputPathSpec,
    ParseError,
    ShellParser,
    ShellSpec,
)
from completer import ShellCompleter


class PTShellCompleter(Completer):
    def __init__(self, completer: ShellCompleter) -> None:
        self.completer = completer

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        seen = set()
        for completion in self.completer.complete(document.text):
            if completion.text and completion not in seen:
                seen.add(completion)
                yield Completion(text=completion.text, display=completion.display)


# NOTE: If ShellParser becomes a Parser, remove references to ShellParser.
class PTShellAutoSuggest(AutoSuggest):
    def __init__(self, completer: ShellCompleter) -> None:
        self.completer = completer

    def get_suggestion(self, buffer: Buffer, document: Document) -> Suggestion | None:
        completions = self.completer.complete(buffer.text)
        if len(completions) == 1:
            (c,) = completions
            return Suggestion(c.text)
        return None


validation_message = ""


def toolbar():
    global validation_message
    return validation_message


def cd(args: CommandData):
    _, dir = args
    os.chdir(dir)


def ls(args: CommandData):
    dir = Path(".") if len(args) == 1 else args[1]
    for path in dir.iterdir():
        print(path.relative_to(dir).as_posix())


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

kb = KeyBindings()


@kb.add("enter", filter=~has_completions)
def _(event):
    text = event.app.current_buffer.document.text
    data = parser.parse(text)
    if not isinstance(data, ParseError):
        event.app.current_buffer.validate_and_handle()
    else:
        global validation_message
        # TODO: Add error messages for:
        # - <ENTER> on no command
        # - Missing argument
        # - Invalid path
        validation_message = "..."


@kb.add("enter", filter=has_completions)
def _(event):
    buf = event.app.current_buffer
    current_completion = buf.complete_state.current_completion
    if current_completion is not None:
        buf.apply_completion(current_completion)


@kb.add("<any>")
def _(event):
    key = event.key_sequence[0].key
    text = event.app.current_buffer.text
    global validation_message
    valid_chars = set(c.text[0] for c in completer.complete(text) if c.text)
    if key in valid_chars:
        event.app.current_buffer.insert_text(key)
        validation_message = ""
    else:
        # BUG: lost enter is not valid here
        validation_message = f"{key} is not valid here"


session = PromptSession()

style = Style.from_dict(
    {
        # User input (default text).
        "": "#ff0066",
        # Prompt.
        "dollar": "#00aa00",
        "path": "ansicyan underline",
    }
)

while True:
    cwd = Path.cwd().as_posix()
    message = [("class:path", cwd), ("class:dollar", "$ ")]
    text = session.prompt(
        message,
        style=style,
        completer=PTShellCompleter(completer),
        complete_while_typing=False,
        key_bindings=kb,
        bottom_toolbar=toolbar,
        auto_suggest=PTShellAutoSuggest(completer),
        # enable_history_search=True,
        # rprompt=toolbar,
    )
    cmd = parser.parse(text)
    assert not isinstance(cmd, ParseError)
    print(cmd)
    cmd.callback(cmd.data)
