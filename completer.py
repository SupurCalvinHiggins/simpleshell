import itertools as it
import os
from pathlib import Path
from typing import Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document


class PathCompleter(Completer):
    def __init__(
        self,
        only_directories: bool = False,
    ) -> None:
        self.only_directories = only_directories

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        # The base directory is the part before the last slash. The part after the last
        # slash should be completed.
        text = document.text_before_cursor
        directory, prefix = os.path.split(text)

        # Only allow a sequence of zero or more .. at the start of the path.
        candidates = list(Path(directory).iterdir())
        if not directory or directory.endswith(".."):
            candidates.append(Path(".."))
        candidates.sort()

        # TODO: disallow returning to exited directory(?)

        for path in candidates:
            if self.only_directories and not path.is_dir():
                continue
            name = path.name + "/" if path.is_dir() else path.name
            if not name.startswith(prefix):
                continue
            completion = name[len(prefix) :]
            yield Completion(
                text=completion,
                start_position=0,
                display=name,
            )


if __name__ == "__main__":
    completer = PathCompleter(only_directories=True)

    for path in ["", ".", "..", "../", "tes", "test/", "../shell/"]:
        print(path)
        for completion in completer.get_completions(Document(path), None):
            print(completion.text.rjust(20))
