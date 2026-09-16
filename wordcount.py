#!/usr/bin/env python3
"""wordcount - count whitespace-separated words in one UTF-8 text file.

This module is the entire product: one file, standard library only, no
configuration and no third-party packages.

Usage
    python3 wordcount.py <file>        print the word count (exit 0)
    python3 wordcount.py --help        usage, examples and exit codes (exit 0)
    python3 wordcount.py --self-test   run the built-in smoke suite (exit 0/1)

The smoke suite is plain ``unittest`` and is also reachable from the standard
runner:

    python3 -m unittest wordcount -v

It lives in this same file because the deliverable is a single module.

Design tokens committed for this build (calm-precise, terminal dark)
    accent    oklch(0.58 0.12 205)  ==  #008d9c
    surface   terminal dark - the only honest CLI surface
    type      system monospace, compact density, aligned columns
    layout    box-drawing rules, help-first output, aligned columns
    signal    one accent for primary status; colour never carries it alone

The accent is emitted as a truecolour escape only when the stream is a TTY and
``NO_COLOR`` / ``TERM=dumb`` are unset, so piped output stays plain and the
count remains byte-for-byte scriptable.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, List, Sequence, Tuple

PROG = "wordcount.py"

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_ERROR = 2

DESCRIPTION = "Count whitespace-separated words in one UTF-8 text file."

# --- design tokens ---------------------------------------------------------
ACCENT_OKLCH = "oklch(0.58 0.12 205)"
ACCENT_HEX = "#008d9c"
_ACCENT_RGB = (0x00, 0x8D, 0x9C)

_BOX_HORIZONTAL = "\u2500"
_ASCII_HORIZONTAL = "-"
_HELP_RULE_WIDTH = 58

_HELP_EXAMPLES: Tuple[Tuple[str, str], ...] = (
    (f"python {PROG} notes.txt", "count the words in a note file"),
    (f"python {PROG} report.md", "count the words in a report"),
)

_HELP_SUITE: Tuple[Tuple[str, str], ...] = (
    (f"python {PROG} --self-test", "run the built-in tests"),
    ("python3 -m unittest wordcount", "same suite, stdlib runner"),
)


class InputError(Exception):
    """The requested path cannot be read as a UTF-8 text file."""


# --- output styling --------------------------------------------------------

def _colour_enabled(stream: Any) -> bool:
    """True only when *stream* is an interactive terminal that wants colour."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    isatty = getattr(stream, "isatty", None)
    if isatty is None:
        return False
    try:
        return bool(isatty())
    except (OSError, ValueError):
        return False


def _accent(text: str, stream: Any) -> str:
    """Wrap *text* in the committed accent colour when *stream* is a TTY."""
    if not _colour_enabled(stream):
        return text
    red, green, blue = _ACCENT_RGB
    return "\x1b[38;2;{};{};{}m{}\x1b[0m".format(red, green, blue, text)


def _horizontal() -> str:
    """Box-drawing rule character, or an ASCII fallback for ASCII streams."""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        _BOX_HORIZONTAL.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return _ASCII_HORIZONTAL
    return _BOX_HORIZONTAL


# --- help text -------------------------------------------------------------

def _columns(rows: Tuple[Tuple[str, str], ...]) -> List[str]:
    """Lay rows out as aligned two-column lines (the committed layout)."""
    column = max(len(left) for left, _ in rows) + 3
    return ["  {}{}".format(left.ljust(column), right) for left, right in rows]


def _epilog() -> str:
    rule = _horizontal() * _HELP_RULE_WIDTH

    lines = [rule, _accent("Examples", sys.stdout), rule]
    lines += _columns(_HELP_EXAMPLES)
    lines += [
        "",
        _accent("Exit codes", sys.stdout),
        "  0   the count was printed to stdout",
        "  1   a built-in smoke test case failed",
        "  2   usage error or unreadable input; the reason went to stderr",
        "",
        _accent("Smoke suite", sys.stdout),
    ]
    lines += _columns(_HELP_SUITE)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (help exits 0, usage errors exit 2)."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        usage=f"{PROG} <file>",
        description=DESCRIPTION,
        epilog=_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        nargs="?",
        metavar="<file>",
        help="path to the UTF-8 text file to count",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the built-in smoke test suite and exit",
    )
    return parser


# --- core ------------------------------------------------------------------

def count_words(path: str) -> int:
    """Return the number of whitespace-separated words in *path*.

    The file is streamed line by line, so memory use is proportional to the
    longest line rather than the file size. Raises :class:`InputError` with a
    user-facing message for every rejected input.
    """
    if not os.path.exists(path):
        raise InputError(f"file not found: {path}")
    if not os.path.isfile(path):
        raise InputError(f"not a file: {path}")

    try:
        with open(path, "r", encoding="utf-8") as handle:
            return sum(len(line.split()) for line in handle)
    except UnicodeDecodeError as exc:
        raise InputError(f"cannot decode as UTF-8: {path}") from exc
    except PermissionError as exc:
        raise InputError(f"cannot read: {path}") from exc
    except OSError as exc:
        raise InputError(f"cannot read: {path}") from exc


# --- built-in smoke suite --------------------------------------------------

def _smoke_suite() -> type:
    """Build the smoke test case class.

    ``unittest`` (with ``builtins``/``contextlib``/``io``/``tempfile``) is
    imported here rather than at module level so that running the CLI imports
    nothing beyond ``argparse``/``os``/``sys`` and starts immediately.
    """
    import builtins
    import contextlib
    import io
    import tempfile
    import unittest

    class WordcountSmokeTest(unittest.TestCase):
        """One case per core behaviour: counting, usage, and validation."""

        def setUp(self) -> None:
            self._tmp = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp.cleanup)

        def write_bytes(self, name: str, payload: bytes) -> str:
            path = os.path.join(self._tmp.name, name)
            with open(path, "wb") as handle:
                handle.write(payload)
            return path

        def write_text(self, name: str, text: str) -> str:
            return self.write_bytes(name, text.encode("utf-8"))

        def run_cli(self, argv: Sequence[str]) -> Tuple[int, str, str]:
            """Run main() in-process; returns (exit code, stdout, stderr)."""
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = main(list(argv))
                except SystemExit as stop:  # argparse: --help and usage errors
                    code = stop.code if isinstance(stop.code, int) else EXIT_FAILURE
            return code, out.getvalue(), err.getvalue()

        def failing_open(self, target: str, error: OSError) -> Tuple[Any, Any]:
            """Return (real_open, replacement) that raises *error* for *target*."""
            real_open = builtins.open

            def replacement(path: Any, *args: Any, **kwargs: Any) -> Any:
                if os.fspath(path) == target:
                    raise error
                return real_open(path, *args, **kwargs)

            return real_open, replacement

        # -- counting ----------------------------------------------------

        def test_counts_words_in_a_file(self) -> None:
            sample = self.write_text("sample.txt", "hello world")

            code, out, err = self.run_cli([sample])

            self.assertEqual(code, EXIT_OK)
            self.assertEqual(out, "2\n")
            self.assertEqual(err, "")

        def test_ignores_surrounding_and_repeated_whitespace(self) -> None:
            sample = self.write_text(
                "sample.txt", "\n  hello \t\t world \n\n   farewell   moon  \r\n"
            )

            code, out, _ = self.run_cli([sample])

            self.assertEqual(code, EXIT_OK)
            self.assertEqual(out, "4\n")

        def test_counts_multiline_utf8_file(self) -> None:
            sample = self.write_text("unicode.txt", "caf\u00e9 na\u00efve\nr\u00e9sum\u00e9\n")

            self.assertEqual(count_words(sample), 3)

        def test_empty_file_counts_zero(self) -> None:
            empty = self.write_text("empty.txt", "")

            code, out, err = self.run_cli([empty])

            self.assertEqual(code, EXIT_OK)
            self.assertEqual(out, "0\n")
            self.assertEqual(err, "")

        def test_streams_a_large_file(self) -> None:
            rows = 2_000
            big = self.write_text("big.txt", "alpha beta gamma delta epsilon\n" * rows)

            self.assertEqual(count_words(big), rows * 5)

        def test_input_file_is_left_untouched(self) -> None:
            sample = self.write_text("notes.txt", "do not touch me\n")
            with open(sample, "rb") as handle:
                before = handle.read()

            self.run_cli([sample])

            with open(sample, "rb") as handle:
                self.assertEqual(handle.read(), before)
            self.assertTrue(os.path.isfile(sample))

        # -- usage -------------------------------------------------------

        def test_help_exits_zero_with_usage_and_example(self) -> None:
            code, out, err = self.run_cli(["--help"])

            self.assertEqual(code, EXIT_OK)
            self.assertIn(f"usage: {PROG} <file>", out)
            self.assertIn(f"python {PROG} notes.txt", out)
            self.assertEqual(err, "")

        def test_no_arguments_is_a_usage_error(self) -> None:
            code, out, err = self.run_cli([])

            self.assertEqual(code, EXIT_ERROR)
            self.assertEqual(out, "")
            self.assertIn(f"usage: {PROG} <file>", err)

        def test_two_files_is_a_usage_error(self) -> None:
            first = self.write_text("a.txt", "one\n")
            second = self.write_text("b.txt", "two\n")

            code, out, err = self.run_cli([first, second])

            self.assertEqual(code, EXIT_ERROR)
            self.assertEqual(out, "")
            self.assertNotEqual(err, "")

        def test_self_test_flag_is_parsed_without_recursing(self) -> None:
            self.assertTrue(build_parser().parse_args(["--self-test"]).self_test)
            self.assertFalse(build_parser().parse_args(["notes.txt"]).self_test)

        # -- validation --------------------------------------------------

        def test_missing_file_is_reported(self) -> None:
            missing = os.path.join(self._tmp.name, "nope.txt")

            code, out, err = self.run_cli([missing])

            self.assertEqual(code, EXIT_ERROR)
            self.assertEqual(out, "")
            self.assertEqual(err, f"error: file not found: {missing}\n")

        def test_directory_is_reported(self) -> None:
            folder = os.path.join(self._tmp.name, "some_directory")
            os.makedirs(folder, exist_ok=True)

            code, _, err = self.run_cli([folder])

            self.assertEqual(code, EXIT_ERROR)
            self.assertEqual(err, f"error: not a file: {folder}\n")

        def test_invalid_utf8_is_reported(self) -> None:
            bad = self.write_bytes("bad.txt", b"hello \xff\xfe world\n")

            code, out, err = self.run_cli([bad])

            self.assertEqual(code, EXIT_ERROR)
            self.assertEqual(out, "")
            self.assertEqual(err, f"error: cannot decode as UTF-8: {bad}\n")

        def test_unreadable_file_is_reported(self) -> None:
            locked = self.write_text("locked.txt", "secret words here\n")
            real_open, deny = self.failing_open(locked, PermissionError(13, "denied"))
            builtins.open = deny
            try:
                code, out, err = self.run_cli([locked])
            finally:
                builtins.open = real_open

            self.assertEqual(code, EXIT_ERROR)
            self.assertEqual(out, "")
            self.assertEqual(err, f"error: cannot read: {locked}\n")

        def test_unexpected_oserror_is_reported(self) -> None:
            broken = self.write_text("broken.txt", "words\n")
            real_open, fail = self.failing_open(broken, OSError(5, "Input/output error"))
            builtins.open = fail
            try:
                code, out, err = self.run_cli([broken])
            finally:
                builtins.open = real_open

            self.assertEqual(code, EXIT_ERROR)
            self.assertEqual(out, "")
            self.assertEqual(err, f"error: cannot read: {broken}\n")

        # -- end to end --------------------------------------------------

        def test_end_to_end_via_subprocess(self) -> None:
            import subprocess

            sample = self.write_text("sample.txt", "hello world")
            result = subprocess.run(
                [sys.executable, os.path.abspath(__file__), sample],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, EXIT_OK)
            self.assertEqual(result.stdout, "2\n")
            self.assertEqual(result.stderr, "")

    return WordcountSmokeTest


def run_self_test() -> int:
    """Run the built-in smoke suite; returns 0 when every case passes."""
    import unittest

    suite = unittest.TestLoader().loadTestsFromTestCase(_smoke_suite())
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    return EXIT_OK if result.wasSuccessful() else EXIT_FAILURE


def load_tests(loader: Any, tests: Any, pattern: Any) -> Any:
    """unittest protocol hook: makes ``python3 -m unittest wordcount`` work."""
    return loader.loadTestsFromTestCase(_smoke_suite())


# --- entry point -----------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI; returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if args.file is None:
        parser.error("the following arguments are required: <file>")

    try:
        total = count_words(args.file)
    except InputError as error:
        # The whole line is wrapped so the message stays contiguous even when
        # the accent escape is present (a TTY-only concern).
        sys.stderr.write(_accent(f"error: {error}", sys.stderr) + "\n")
        return EXIT_ERROR

    sys.stdout.write(f"{total}\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
