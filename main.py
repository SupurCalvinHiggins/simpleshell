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

from config import make_shell
from engine import Completer as EngineCompleter
from engine import CompletionError, ParseError


def is_err(x):
    return isinstance(x, (CompletionError, ParseError))


class CompleterAdapter(Completer):
    def __init__(self, completer: EngineCompleter) -> None:
        self.completer = completer

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        seen = set()
        completions_or_err = self.completer.complete(document.text)
        if is_err(completions_or_err):
            return
        completions = completions_or_err
        for completion in completions:
            if completion.text and completion not in seen:
                seen.add(completion)
                yield Completion(text=completion.text, display=completion.display)


class AutoSuggestAdapter(AutoSuggest):
    def __init__(self, completer: EngineCompleter) -> None:
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


kb = KeyBindings()

parser, completer = make_shell()


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
        validation_message = data.msg


@kb.add("enter", filter=has_completions)
def _(event):
    buf = event.app.current_buffer
    current_completion = buf.complete_state.current_completion
    if current_completion is not None:
        buf.apply_completion(current_completion)
    else:
        # TODO: do the same as other <enter> event.
        # this will fix the BUG where enter on valid doesnt work when there is
        # a completion popup
        pass


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
        completer=CompleterAdapter(completer),
        complete_while_typing=False,
        key_bindings=kb,
        bottom_toolbar=toolbar,
        auto_suggest=AutoSuggestAdapter(completer),
        # enable_history_search=True,
        # rprompt=toolbar,
    )
    cmd = parser.parse(text)
    assert not isinstance(cmd, ParseError)
    print(cmd)
    cmd.callback(cmd.data)
