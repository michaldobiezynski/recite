"""Custom Textual widgets for recite."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from .aligners import WordTiming


@dataclass(frozen=True)
class SentenceState:
    PAST = "past"
    UPCOMING = "upcoming"
    CURRENT = "current"


class SentenceWidget(Static):
    """Renders one sentence with optional per-word highlight.

    States:
      - past:     rendered dim/faint
      - upcoming: rendered in default body colour
      - current:  rendered prominent, with the current word highlighted
    """

    DEFAULT_CSS = """
    SentenceWidget {
        padding: 0 1;
        margin-bottom: 1;
        width: 100%;
        height: auto;
    }
    SentenceWidget.-past {
        color: $text-muted;
        text-style: dim;
    }
    SentenceWidget.-upcoming {
        color: $text;
    }
    SentenceWidget.-current {
        color: $text;
        text-style: bold;
        background: $boost;
    }
    """

    state: reactive[str] = reactive(SentenceState.UPCOMING, layout=False)
    current_word_idx: reactive[int] = reactive(-1, layout=False)

    def __init__(self, sentence: str, index: int, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.sentence = sentence
        self.index = index
        self.timings: list[WordTiming] = []
        self._update_classes()

    def set_timings(self, timings: list[WordTiming]) -> None:
        self.timings = timings
        self._refresh()

    def set_state(self, state: str) -> None:
        self.state = state
        self._update_classes()
        self._refresh()

    def set_word(self, word_idx: int) -> None:
        if word_idx != self.current_word_idx:
            self.current_word_idx = word_idx
            self._refresh()

    def _update_classes(self) -> None:
        self.remove_class("-past", "-upcoming", "-current")
        self.add_class(f"-{self.state}")

    def _refresh(self) -> None:
        if not self.timings or self.state != SentenceState.CURRENT:
            self.update(Text(self.sentence))
            return

        text = Text(self.sentence)
        if 0 <= self.current_word_idx < len(self.timings):
            timing = self.timings[self.current_word_idx]
            # Highlight the live word with a brighter style.
            text.stylize("bold reverse", timing.start_idx, timing.end_idx)
        self.update(text)
