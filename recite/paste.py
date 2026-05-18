"""Paste-text screen — shown when no input source is available, or on --paste.

Runs as a separate App that returns the entered text via `App.exit(value)`.
The main `ReciteApp` then runs in a second `App.run()` invocation with that
text. Two sequential apps is simpler than nesting screens for this case.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static, TextArea


class PasteApp(App[str | None]):
    """Show a TextArea, return its contents on Ctrl+S / F5, None on Esc."""

    CSS = """
    Screen {
        background: $surface;
    }
    #hint {
        dock: top;
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
        yield Static(
            "paste text below — Ctrl+S or F5 to start, Esc to cancel",
            id="hint",
        )
        yield TextArea(id="paste-area", soft_wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "recite"
        self.sub_title = "paste"
        self.query_one(TextArea).focus()

    def action_start(self) -> None:
        text = self.query_one(TextArea).text
        self.exit(text if text.strip() else None)

    def action_cancel(self) -> None:
        self.exit(None)
