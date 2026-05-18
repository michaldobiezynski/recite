"""CLI entry point for recite."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .app import ReciteApp
from .splitter import split_sentences


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="recite",
        description="A TUI text-to-speech player for macOS, with word-level highlighting.",
        epilog=(
            "Reads from a file argument, piped stdin, or the clipboard (pbpaste) in that order.\n"
            "In the app: space=play/pause, j/k=next/prev, r=replay, +/-=faster/slower, "
            "v=voice, q=quit."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", help="path to a text file (omit to read clipboard/stdin)")
    parser.add_argument("--voice", default="Daniel", help="voice to use (default: Daniel)")
    parser.add_argument(
        "--rate",
        type=int,
        default=0,
        help="speech rate in WPM (default: system default)",
    )
    parser.add_argument(
        "--align",
        choices=("heuristic", "aeneas"),
        default="heuristic",
        help=(
            "word-timing aligner. 'heuristic' is instant and dep-free. "
            "'aeneas' is more accurate but requires `pipx install recite[align]` "
            "and `brew install espeak ffmpeg`."
        ),
    )
    parser.add_argument(
        "--paste",
        action="store_true",
        help="open a paste-text screen instead of reading file/stdin/clipboard",
    )
    args = parser.parse_args()

    if not shutil.which("say"):
        sys.stderr.write("recite: `say` not found on PATH — macOS is required.\n")
        return 1
    if not shutil.which("afplay"):
        sys.stderr.write("recite: `afplay` not found on PATH — macOS is required.\n")
        return 1
    if not shutil.which("afinfo"):
        sys.stderr.write("recite: `afinfo` not found on PATH — macOS is required.\n")
        return 1

    text = "" if args.paste else _load_input(args.file)
    if not text.strip():
        text = _open_paste_screen()
        if not text:
            return 0

    while True:
        sentences = split_sentences(text)
        if not sentences:
            sys.stderr.write("recite: no readable sentences found in input.\n")
            text = _open_paste_screen()
            if not text:
                return 1
            continue

        app = ReciteApp(
            sentences=sentences,
            voice=args.voice,
            rate=args.rate,
            align=args.align,
        )
        result = app.run()

        # Ctrl+N in ReciteApp exits with "paste" so we loop back to the
        # paste screen. Any other exit (q/Esc/Ctrl+Q/finished) ends the CLI.
        if result != "paste":
            return 0

        text = _open_paste_screen()
        if not text:
            return 0


def _open_paste_screen() -> str:
    """Show the paste TextArea and return non-empty text, or empty on cancel."""
    from .paste import PasteApp
    text = PasteApp().run() or ""
    return text if text.strip() else ""


def _load_input(file_arg: str | None) -> str:
    if file_arg:
        path = Path(file_arg)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"recite: could not read {file_arg}: {exc}\n")
            sys.exit(1)
    if not sys.stdin.isatty():
        text = sys.stdin.read()
        # Without this, the TUI launches but never receives any keystrokes
        # because stdin is the (now-EOF) pipe instead of the terminal.
        _reattach_stdin_to_tty()
        return text
    if shutil.which("pbpaste"):
        try:
            return subprocess.check_output(["pbpaste"], text=True)
        except subprocess.CalledProcessError:
            return ""
    return ""


def _reattach_stdin_to_tty() -> None:
    """Swap stdin (fd 0) for /dev/tty so the TUI can read keystrokes after
    piped input has been consumed. Silently no-ops when there is no
    controlling tty (e.g. cron, daemonised)."""
    try:
        tty_fd = os.open("/dev/tty", os.O_RDONLY)
    except OSError:
        return
    os.dup2(tty_fd, 0)
    os.close(tty_fd)
    sys.stdin = os.fdopen(0, "r")


if __name__ == "__main__":
    sys.exit(main())
