"""Paste-text screen, shown when no input source is available, or on --paste.

Runs as a separate App that returns the entered text via `App.exit(value)`.
The main `ReciteApp` then runs in a second `App.run()` invocation with that
text. Two sequential apps is simpler than nesting screens for this case.
"""

from __future__ import annotations

import re

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static, TextArea

# The site's step 03 mockup quotes ETA at 200 wpm; using the same yardstick
# keeps the paste-screen readout consistent with the marketing copy.
ETA_WPM = 200

# Lines that begin with one of these markers are kept as their own paragraph
# rather than being merged with the previous line. Covers ASCII bullets,
# the unicode bullet, period-style numbered lists (`1.`) and paren-style
# (`1)`). The pattern requires whitespace after the marker so that a stray
# minus sign or asterisk inside prose is not misread as a list start.
_LIST_MARKER_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s")
_HEADING_RE = re.compile(r"^#+\s")


def reflow_paste_text(raw: str) -> str:
    """Collapse terminal-style soft wraps in pasted text.

    Single newlines inside a logical paragraph are merged to a space so
    sentences travel intact to the splitter; blank lines, list items, and
    Markdown headings are preserved as their own paragraph (joined with a
    blank line so the splitter still sees a paragraph break).

    Why: text copied out of a terminal (Claude Code, man pages, less
    output) carries the terminal's hard-wrap newlines. The splitter treats
    every newline as a paragraph boundary, so sentences play in fragments.
    Reflowing on the paste path fixes the common case without changing
    stdin/file behaviour for callers that hand-craft their line breaks.
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


class PasteApp(App[str | None]):
    """Show a TextArea, return its contents on Ctrl+S / F5, None on Esc.

    The hint line below the title reports live `chars · words · ETA` plus a
    `● ready` indicator once the buffer has content, mirroring the step 03
    mockup on recite-site."""

    CSS = """
    Screen {
        background: $surface;
    }
    #hint {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    TextArea {
        height: 1fr;
        margin: 1 2 0 2;
        border: round $primary;
    }
    """

    BINDINGS = [
        Binding("ctrl+s,f5", "start", "start", priority=True),
        Binding("escape", "cancel", "cancel", priority=True),
        Binding("ctrl+q", "cancel", "cancel", priority=True, show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(self._build_hint_text(), id="hint")
        yield TextArea(id="paste-area", soft_wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "recite"
        self.sub_title = "paste"
        self.query_one(TextArea).focus()
        self._refresh_hint()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._refresh_hint()

    def action_start(self) -> None:
        text = reflow_paste_text(self.query_one(TextArea).text)
        self.exit(text if text else None)

    def action_cancel(self) -> None:
        self.exit(None)

    def _current_text(self) -> str:
        try:
            return self.query_one(TextArea).text
        except Exception:
            return ""

    def _build_hint_text(self) -> str:
        """Compose the dock-top hint. Pure: testable without rendering.

        Empty buffer → instruction prompt.
        Non-empty buffer → `N chars · M words · ~K sec @ 200 wpm  ● ready`,
        mirroring recite-site's step 03 paste-screen mockup."""
        text = self._current_text()
        if not text.strip():
            return "paste text below. Ctrl+S or F5 to start, Esc to cancel"
        chars = len(text)
        words = len(text.split())
        eta = round(words / ETA_WPM * 60) if words else 0
        return (
            f"{chars} chars · {words} words · ~{eta} sec @ {ETA_WPM} wpm   "
            f"● ready. Ctrl+S to start, Esc to cancel"
        )

    def _refresh_hint(self) -> None:
        try:
            self.query_one("#hint", Static).update(self._build_hint_text())
        except Exception:
            pass
