import itertools as it
import os
from pathlib import Path
from typing import Iterable, Iterator

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    NestedCompleter,
    WordCompleter,
)
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_completions
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator

from completer import PathCompleter

kb = KeyBindings()
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

validation_message = ""


@kb.add("backspace")
def handle_backspace(event):
    event.app.current_buffer.delete_before_cursor()


@kb.add("c-c")
def handle_interrupt(event):
    event.app.exit()


@kb.add("enter", filter=~has_completions)
def handle_enter(event):
    global validation_message
    text = event.app.current_buffer.document.text
    parts = text.split()
    if len(parts) == 0:
        validation_message = (
            "<ENTER> executes the current command but no command was provided"
        )
        return

    cmd = parts[0]
    if cmd == "cd":
        if len(parts) != 2:
            validation_message = "cd requires a path argument"
            return
        path = Path(parts[1])
        if not path.exists():
            validation_message = "path does not exist"
            return
    elif cmd == "ls":
        if len(parts) != 1:
            path = Path(parts[1])
            if not path.exists():
                validation_message = "path does not exist"
                return
    event.app.current_buffer.validate_and_handle()


@kb.add("enter", filter=has_completions)
def _(event):
    buf = event.app.current_buffer
    current_completion = buf.complete_state.current_completion
    if current_completion is not None:
        buf.apply_completion(current_completion)


@kb.add("left")
def handle_left(event):
    event.app.current_buffer.cursor_left()


@kb.add("right")  # needed if you have ghost text
def handle_right(event):
    event.app.current_buffer.cursor_right()


def toolbar():
    global validation_message
    return validation_message


# concepts:
# - MUST type something (e.g. the command name, required arguments to command)
# - MAY type something (e.g. optional arguments, non-prefix free required arguments)
# - CANT type something (e.g. no completions left on final argument)
completer = NestedCompleter.from_nested_dict(
    {
        "cd": PathCompleter(only_directories=True),
        "ls": PathCompleter(only_directories=True),
    }
)

# print(
#     list(FullPathCompleter(only_directories=True).get_completions(Document(".."), None))
# )


class CompleterAutoSuggest(AutoSuggest):
    def get_suggestion(self, buffer, document):
        completions = list(buffer.completer.get_completions(document, None))
        if len(completions) == 1:
            (c,) = completions
            return Suggestion(c.text[-c.start_position :])
        return None


def get_valid_next_chars(text: str) -> set[str]:
    # if the text is a valid command, then the next valid is space
    if text in ["cd", "ls"]:
        return {" "}
    # TODO: if the text is a valid directory, then the next valid includes /
    # NOTE: it might be better to just modify pathcompleter to handle .. and autofill / on directories
    document = Document(text)
    completions = list(completer.get_completions(document, None))
    # print(completions)
    res = set(c.text[-c.start_position] for c in completions if c.text)
    # print(res)
    return res


@kb.add("<any>")
def handle_any(event):
    key = event.key_sequence[0].key
    current = event.app.current_buffer.text
    global validation_message
    if key in get_valid_next_chars(current):
        event.app.current_buffer.insert_text(key)
        validation_message = ""
    else:
        validation_message = f"{key} is not valid here"


while True:
    cwd = Path.cwd().as_posix()
    message = [("class:path", cwd), ("class:dollar", "$ ")]
    text = session.prompt(
        message,
        style=style,
        completer=completer,
        complete_while_typing=False,
        key_bindings=kb,
        bottom_toolbar=toolbar,
        auto_suggest=CompleterAutoSuggest(),
        # rprompt=toolbar,
    )
    parts = text.split()
    cmd = parts[0]
    if cmd == "cd":
        path = Path(parts[1])
        os.chdir(path)
    elif cmd == "ls":
        path = Path(".") if len(parts) == 1 else Path(parts[1])
        for filepath in path.iterdir():
            print(filepath.relative_to(path).as_posix())
