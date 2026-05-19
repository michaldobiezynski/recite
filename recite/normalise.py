"""Text normalisation for input from terminal sources.

`reflow_terminal_wraps` collapses single newlines inside a logical paragraph
into spaces so that text copied out of a terminal (Claude Code, man, less,
piped output) reaches the sentence splitter as a single paragraph rather
than fragmenting on every hard wrap inserted by the producing program.

Blank lines, list markers (`-`, `*`, `•`, `1.`, `1)`) and ATX headings
(`# `, `## `, ...) are preserved as their own paragraph because they
encode real structural intent, not terminal-width accidents.

Called from both the paste path (`PasteApp.action_start` in `paste.py`)
and the stdin/file/clipboard path (`__main__._load_input` is wrapped by
`main` before the splitter runs). The function is idempotent for
already-blank-line-separated input so applying it twice is harmless.
"""

from __future__ import annotations

import re

# Lines beginning with one of these markers are kept as their own paragraph
# rather than being merged with the previous line. The trailing `\s` matches
# the CommonMark rule that a list marker (or ATX heading) requires whitespace
# after it, so stray `-`, `*` or `#` inside prose are not misread as
# structure.
_LIST_MARKER_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s")
_HEADING_RE = re.compile(r"^#+\s")


def reflow_terminal_wraps(raw: str) -> str:
    """Collapse single newlines inside paragraphs; preserve structural breaks.

    See module docstring for the scope decision. Returns `""` for empty or
    whitespace-only input.
    """
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if _LIST_MARKER_RE.match(stripped) or _HEADING_RE.match(stripped):
            flush()
            paragraphs.append(stripped)
            continue
        current.append(stripped)
    flush()
    return "\n\n".join(paragraphs)
