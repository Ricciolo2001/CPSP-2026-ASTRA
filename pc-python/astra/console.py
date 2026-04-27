# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

import logging
import sys
import threading
from typing import Callable


class CustomFormatter(logging.Formatter):
    # ANSI Escape Sequences
    GREY = "\x1b[90m"
    BOLD_RED = "\x1b[1;31m"
    RESET = "\x1b[0m"

    # Level Backgrounds
    BG_DEBUG = "\x1b[46;30m"
    BG_INFO = "\x1b[42;30m"
    BG_WARN = "\x1b[43;30m"
    BG_ERROR = "\x1b[41;37m"
    BG_CRIT = "\x1b[41;1;37m"

    def __init__(self, use_color=True):
        super().__init__()
        self.use_color = use_color

        # Define the two style variations
        time_str = (
            f"{self.GREY}[%(asctime)s]{self.RESET} " if use_color else "[%(asctime)s] "
        )
        msg_norm = "%(message)s"
        msg_err = (
            f"{self.BOLD_RED}%(message)s{self.RESET}" if use_color else "%(message)s"
        )

        if use_color:
            self.formats = {
                logging.DEBUG: time_str
                + f"{self.BG_DEBUG} DEBG {self.RESET} "
                + msg_norm,
                logging.INFO: time_str
                + f"{self.BG_INFO} INFO {self.RESET} "
                + msg_norm,
                logging.WARNING: time_str
                + f"{self.BG_WARN} WARN {self.RESET} "
                + msg_norm,
                logging.ERROR: time_str
                + f"{self.BG_ERROR} ERRO {self.RESET} "
                + msg_err,
                logging.CRITICAL: time_str
                + f"{self.BG_CRIT} CRIT {self.RESET} "
                + msg_err,
            }
        else:
            # Clean, plain format for files/non-tty
            plain_fmt = "[%(asctime)s] %(levelname)-5s %(message)s"
            self.formats = {
                level: plain_fmt
                for level in [
                    logging.DEBUG,
                    logging.INFO,
                    logging.WARNING,
                    logging.ERROR,
                    logging.CRITICAL,
                ]
            }

        self.formatters = {
            level: logging.Formatter(fmt, datefmt="%H:%M:%S")
            for level, fmt in self.formats.items()
        }

    def format(self, record):
        formatter = self.formatters.get(record.levelno, self.formatters[logging.INFO])
        return formatter.format(record)


def basic_config(level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)

    is_tty = sys.stdout.isatty()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CustomFormatter(use_color=is_tty))

    if root.hasHandlers():
        root.handlers.clear()

    root.addHandler(handler)


class LineBuffer:
    """
    Reassemble lines of text from a stream of UTF-8 text chunks, and call a
    callback for each complete line.

    Use feed() to add text chunks to the buffer, the callback will be called
    for each complete line that can be extracted from the buffer, excluding
    the newline character.
    """

    def __init__(self, on_line: Callable[[str], None]) -> None:
        self._buf = ""
        self._on_line = on_line
        self._lock = threading.Lock()

    def feed(self, text: str) -> None:
        to_emit = []
        with self._lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                to_emit.append(line)

        for line in to_emit:
            self._on_line(line)
