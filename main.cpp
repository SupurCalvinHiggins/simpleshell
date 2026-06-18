// adaptive support

// restrict available keystrokes to valid ones(?)
// display hints as typing occurs
// multiple levels of error messages
// multiple levels of help output
// restrict avaiable commands
// need tab autocomplete, shortcuts for navigating within a terminal line
// need Ctrl+C
// Need command history with arrow keys
// backspace
// l/r arrows, l/r + control arrows, control + A (start), control + E (end),
// control + W (delete word back)

// layered approach:
// IO
// Command

// basic design:
// sequence of callbacks (invoke on pattern hit)
// on each line edit, invoke callbacks on the line
// they detect hits on line, and make changes
// display line

// does everything fall into this?
// - restrict keystrokes (delete invalid character)
// - history (rewrite line) (important: stateful)
// - navigation
// - tab complete
// - enter

#include <stdlib.h>
#include <termios.h>
#include <unistd.h>

#include <filesystem>
#include <string>

// https://viewsourcecode.org/snaptoken/kilo/02.enteringRawMode.html
struct termios orig_termios;

void disable_raw_mode() { tcsetattr(STDIN_FILENO, TCSAFLUSH, &orig_termios); }

void enable_raw_mode() {
    tcgetattr(STDIN_FILENO, &orig_termios);
    atexit(disable_raw_mode);

    auto raw = orig_termios;
    raw.c_iflag &= ~(BRKINT | ICRNL | INPCK | ISTRIP | IXON);
    raw.c_oflag &= ~(OPOST);
    raw.c_cflag |= (CS8);
    raw.c_lflag &= ~(ECHO | ICANON | IEXTEN | ISIG);

    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
}

int main(int argc, char* argv[]) {
    enable_raw_mode();

    char c;
    std::string s{"hello world"};
    while (read(STDIN_FILENO, &c, 1) == 1 && c != 'q') {
        if (c == '\t') write(STDOUT_FILENO, s.data(), s.size());
    }
    return 0;
}
