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

from executor import execute
from parser import (
    CommandParser,
    InputDirParser,
    InputFileParser,
    LiteralParser,
    OutputDirParser,
    OutputFileParser,
    PathParser,
    ShellParser,
    make_parser,
)


class ShellCompleter(Completer):
    def __init__(self, parser: ShellParser) -> None:
        self.parser = parser

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        for completion in self.parser.completions(document.text):
            if completion.text:
                yield Completion(text=completion.text, display=completion.display)


# NOTE: If ShellParser becomes a Parser, remove references to ShellParser.
class ShellAutoSuggest(AutoSuggest):
    def __init__(self, parser: ShellParser) -> None:
        self.parser = parser

    def get_suggestion(self, buffer: Buffer, document: Document) -> Suggestion | None:
        completions = self.parser.completions(buffer.text)
        if len(completions) == 1:
            (c,) = completions
            return Suggestion(c.text)
        return None


validation_message = ""


def toolbar():
    global validation_message
    return validation_message


parser = make_parser()

kb = KeyBindings()


@kb.add("enter", filter=~has_completions)
def _(event):
    text = event.app.current_buffer.document.text
    data = parser.parse(text)
    if data is not None:
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
    valid_chars = set(c.text[0] for c in parser.completions(text) if c.text)
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
        completer=ShellCompleter(parser),
        complete_while_typing=False,
        key_bindings=kb,
        bottom_toolbar=toolbar,
        auto_suggest=ShellAutoSuggest(parser),
        # rprompt=toolbar,
    )
    cmd = parser.parse(text)
    execute(cmd)
    continue

    parts = text.split()
    cmd = parts[0]
    if cmd == "cd":
        path = Path(parts[1])
        os.chdir(path)
    elif cmd == "ls":
        path = Path(".") if len(parts) == 1 else Path(parts[1])
        for filepath in path.iterdir():
            print(filepath.relative_to(path).as_posix())
