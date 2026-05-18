"""Textual application for recite."""

from __future__ import annotations

import asyncio
import os
import subprocess
from bisect import bisect_right

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

from .aligners import make_aligner
from .player import Player
from .synth import Synth, available_voices
from .widgets import SentenceState, SentenceWidget


def _fmt_mmss(seconds: float) -> str:
    """Format seconds as zero-padded `MM:SS`. Matches the site's clock format."""
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


class HelpScreen(ModalScreen[None]):
    """Modal overlay listing all keys. Opened by `?`, dismissed by Esc/?/q.
    Lets the main footer stay terse so it doesn't truncate on narrow windows."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-box {
        width: 56;
        height: auto;
        border: round $primary;
        padding: 1 2;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                "recite — keys\n\n"
                "  space         play / pause\n"
                "  j  →  n       next sentence\n"
                "  k  ←  p       previous sentence\n"
                "  r             replay current\n"
                "  g  G          jump to start / end\n"
                "  +  -          speak faster / slower\n"
                "  v             cycle voice\n"
                "  Ctrl+N        new text (paste screen)\n"
                "  ?             show this help\n"
                "  q  Esc        quit\n"
                "  Ctrl+Q        panic exit\n\n"
                "press ? again to close",
                id="help-box",
            ),
        )

class ReciteApp(App[str | None]):
    """A TUI player wrapping `say` with word-level highlighting."""

    CSS = """
    Screen {
        background: $surface;
    }
    #content {
        padding: 1 2;
        height: 1fr;
    }
    #status {
        dock: bottom;
        height: 1;
        padding: 0 2;
        background: $boost;
        color: $text;
    }
    .-playing { color: $success; }
    .-paused { color: $warning; }
    .-idle { color: $text-muted; }
    """

    BINDINGS = [
        # Footer-visible: matches the transport bar the site advertises.
        Binding("space", "play_pause", "play/pause", show=True, priority=True),
        Binding("j,right,n", "next", "next", show=True),
        Binding("k,left,p", "prev", "prev", show=True),
        Binding("v", "cycle_voice", "voice", show=True),
        Binding("plus,equals_sign,equal", "faster", "+wpm", show=True),
        Binding("minus,underscore", "slower", "-wpm", show=True),
        Binding("ctrl+n", "new_text", "new", show=True, priority=True),
        Binding("question_mark", "show_help", "?", show=True, priority=True),
        Binding("q,escape", "quit", "quit", show=True, priority=True),
        # Hidden from footer; surface via the `?` help modal instead.
        Binding("r", "replay", "replay", show=False),
        Binding("g,home", "to_start", "start", show=False),
        Binding("G,end", "to_end", "end", show=False),
        Binding("ctrl+q", "panic_exit", "panic exit", show=False, priority=True),
    ]

    current_idx: reactive[int] = reactive(0, layout=False)
    current_word: reactive[int] = reactive(-1, layout=False)
    is_playing: reactive[bool] = reactive(False, layout=False)
    is_paused: reactive[bool] = reactive(False, layout=False)
    notice: reactive[str] = reactive("", layout=False)

    def __init__(
        self,
        sentences: list[str],
        voice: str,
        rate: int,
        align: str = "heuristic",
    ) -> None:
        super().__init__()
        self.sentences = sentences
        self.voice = voice
        self.rate = rate
        self.align_name = align
        self.voices = available_voices()
        self.voice_idx = self.voices.index(voice) if voice in self.voices else 0

        self.player = Player()
        self.synth: Synth | None = None
        self.sentence_widgets: list[SentenceWidget] = []
        self.auto_advance = True
        self.finished = False
        self.pending_play: int | None = 0  # auto-play first sentence on startup
        self._notice_timer = None
        self._ticker_task: asyncio.Task[None] | None = None
        self._ready_task: asyncio.Task[None] | None = None
        self._player_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with VerticalScroll(id="content"):
            for i, sentence in enumerate(self.sentences):
                w = SentenceWidget(sentence, i)
                self.sentence_widgets.append(w)
                yield w
        yield Static("", id="status")
        # The command-palette hint docks on the right and z-orders over the
        # last footer bindings; at 80 cols that hides `?` and `q quit`. The
        # palette key still works via App.ENABLE_COMMAND_PALETTE; only the
        # visible hint is suppressed.
        yield Footer(show_command_palette=False)

    async def on_mount(self) -> None:
        self.title = "recite"
        self._refresh_subtitle()
        self._mark_widgets()
        self.synth = Synth(self.sentences, self.voice, self.rate, make_aligner(self.align_name))
        self.synth.start(0)
        self._ready_task = asyncio.create_task(self._consume_ready())
        self._player_task = asyncio.create_task(self._consume_player_events())
        self._ticker_task = asyncio.create_task(self._tick())
        self._refresh_status()

    async def on_unmount(self) -> None:
        for task in (self._ticker_task, self._ready_task, self._player_task):
            if task and not task.done():
                task.cancel()
        await self.player.stop()
        if self.synth:
            await self.synth.cancel()
            self.synth.cleanup()

    async def _consume_ready(self) -> None:
        """Listen for sentences becoming render-ready."""
        assert self.synth is not None
        while True:
            try:
                idx = await self.synth.ready_queue.get()
            except asyncio.CancelledError:
                return
            track = self.synth.track(idx)
            if track and track.timings:
                self.sentence_widgets[idx].set_timings(track.timings)
            if self.pending_play == idx:
                await self._start_playback(idx)

    async def _consume_player_events(self) -> None:
        """Advance on natural sentence completion."""
        while True:
            try:
                event = await self.player.events.get()
            except asyncio.CancelledError:
                return
            if event.index != self.current_idx:
                continue
            if not self.auto_advance:
                self.is_playing = False
                self._refresh_status()
                continue
            nxt = self.current_idx + 1
            if nxt >= len(self.sentences):
                self.finished = True
                self.is_playing = False
                self.current_word = -1
                self._refresh_status()
                continue
            await self._navigate_to(nxt)

    async def _tick(self) -> None:
        """30ms ticker drives the per-word highlight update."""
        while True:
            try:
                await asyncio.sleep(0.03)
            except asyncio.CancelledError:
                return
            if not self.player.is_active:
                continue
            assert self.synth is not None
            track = self.synth.track(self.current_idx)
            if not track or not track.timings:
                continue
            pos = self.player.position()
            word_idx = self._word_at(track.timings, pos)
            if word_idx != self.current_word:
                self.current_word = word_idx
                self.sentence_widgets[self.current_idx].set_word(word_idx)

    @staticmethod
    def _word_at(timings: list, position: float) -> int:
        """Find which word's interval contains `position` (binary search by start)."""
        if not timings:
            return -1
        starts = [t.start_s for t in timings]
        # bisect_right returns the index where `position` would be inserted to
        # keep `starts` sorted. The word at that index - 1 is the active one.
        idx = bisect_right(starts, position) - 1
        return max(0, min(idx, len(timings) - 1))

    async def _start_playback(self, idx: int) -> None:
        assert self.synth is not None
        track = self.synth.track(idx)
        if not track or not track.ready or not track.audio_path:
            self.pending_play = idx
            return
        if track.error:
            self._set_notice(f"synth error: {track.error}")
            return
        self.pending_play = None
        self.current_idx = idx
        self.current_word = -1
        self.finished = False
        self._mark_widgets()
        await self.player.play(idx, track.audio_path)
        self.is_playing = True
        self.is_paused = False
        self._refresh_status()
        self._scroll_to_current()

    async def _navigate_to(self, idx: int) -> None:
        if idx < 0:
            idx = 0
        if idx >= len(self.sentences):
            idx = len(self.sentences) - 1
        self.current_idx = idx
        self.current_word = -1
        self._mark_widgets()
        await self._start_playback(idx)

    def _mark_widgets(self) -> None:
        for i, w in enumerate(self.sentence_widgets):
            if i < self.current_idx:
                w.set_state(SentenceState.PAST)
            elif i == self.current_idx:
                w.set_state(SentenceState.CURRENT)
            else:
                w.set_state(SentenceState.UPCOMING)

    def _scroll_to_current(self) -> None:
        if 0 <= self.current_idx < len(self.sentence_widgets):
            try:
                self.query_one("#content", VerticalScroll).scroll_to_widget(
                    self.sentence_widgets[self.current_idx],
                    animate=True,
                    speed=80.0,
                    top=False,
                )
            except Exception:
                pass

    def _set_notice(self, text: str) -> None:
        self.notice = text
        self._refresh_status()
        if self._notice_timer:
            self._notice_timer.stop()
        self._notice_timer = self.set_timer(2.4, self._clear_notice)

    def _clear_notice(self) -> None:
        self.notice = ""
        self._refresh_status()

    def _build_status_text(self) -> str:
        """Compose the status line. Pure: no widget access, fully unit-testable.

        Layout matches the site's transport mockup:
            <state> · <MM:SS / MM:SS> · <idx / total> · voice: X · rate: Y · queue: N synthesised · M pending
        Time clock is only shown while a sentence is active. Queue counter is
        only shown when synthesis is still in flight."""
        bits: list[str] = []
        if self.finished:
            bits.append("○ finished — press space to restart")
        elif self.is_paused:
            bits.append("⏸ paused")
        elif self.is_playing:
            bits.append("▶ playing")
        elif self.pending_play is not None:
            bits.append("◌ synthesising…")
        else:
            bits.append("○ idle")

        time_clock = self._build_time_clock()
        if time_clock:
            bits.append(time_clock)

        bits.append(f"{self.current_idx + 1} / {len(self.sentences)}")
        bits.append(f"voice: {self.voices[self.voice_idx]}")
        bits.append("rate: " + (f"{self.rate} wpm" if self.rate > 0 else "default"))

        queue = self._build_queue_indicator()
        if queue:
            bits.append(queue)

        if self.notice:
            bits.append(self.notice)
        return " · ".join(bits)

    def _build_time_clock(self) -> str:
        """Return `MM:SS / MM:SS` for the current track, or empty when not playing."""
        if not (self.is_playing or self.is_paused):
            return ""
        elapsed = self.player.position()
        total = 0.0
        if self.synth is not None:
            track = self.synth.track(self.current_idx)
            if track is not None:
                total = track.duration_s
        return f"{_fmt_mmss(elapsed)} / {_fmt_mmss(total)}"

    def _build_queue_indicator(self) -> str:
        """Show `queue: N synthesised · M pending` only while pending > 0."""
        if self.synth is None:
            return ""
        ready = sum(1 for t in self.synth._tracks if t.ready)
        pending = len(self.synth._tracks) - ready
        if pending <= 0:
            return ""
        return f"queue: {ready} synthesised · {pending} pending"

    def _refresh_subtitle(self) -> None:
        """Format: `<voice> @ <rate> wpm · aligner: <align>`. Matches the site
        hero title bar `recite · daniel @ 200 wpm · aligner: heuristic`."""
        voice = self.voices[self.voice_idx].lower() if self.voices else self.voice.lower()
        rate_label = f"{self.rate} wpm" if self.rate > 0 else "default rate"
        self.sub_title = f"{voice} @ {rate_label} · aligner: {self.align_name}"

    def _refresh_status(self) -> None:
        try:
            self.query_one("#status", Static).update(self._build_status_text())
        except Exception:
            pass

    # ─── Actions ─────────────────────────────────────────────────────────

    async def action_play_pause(self) -> None:
        if self.finished:
            self.finished = False
            await self._navigate_to(0)
            return
        if not self.player.is_active:
            await self._start_playback(self.current_idx)
            return
        await self.player.toggle()
        self.is_paused = self.player.is_paused
        self._refresh_status()

    async def action_next(self) -> None:
        self.auto_advance = True
        await self._navigate_to(self.current_idx + 1)

    async def action_prev(self) -> None:
        self.auto_advance = True
        await self._navigate_to(self.current_idx - 1)

    async def action_replay(self) -> None:
        self.auto_advance = True
        await self._start_playback(self.current_idx)

    async def action_to_start(self) -> None:
        self.auto_advance = True
        await self._navigate_to(0)

    async def action_to_end(self) -> None:
        self.auto_advance = False
        await self._navigate_to(len(self.sentences) - 1)

    async def action_faster(self) -> None:
        await self._adjust_rate(+20)

    async def action_slower(self) -> None:
        await self._adjust_rate(-20)

    async def _adjust_rate(self, delta: int) -> None:
        base = self.rate or 180
        base = max(120, min(320, base + delta))
        self.rate = base
        self._refresh_subtitle()
        self._set_notice(f"rate → {base} wpm")
        await self._resynth_from_next()

    async def action_cycle_voice(self) -> None:
        self.voice_idx = (self.voice_idx + 1) % len(self.voices)
        self.voice = self.voices[self.voice_idx]
        self._refresh_subtitle()
        self._set_notice(f"voice → {self.voice}")
        await self._resynth_from_next()

    async def _resynth_from_next(self) -> None:
        """Swap the synth and rebuild from the NEXT sentence forward.

        The current sentence keeps playing with its existing audio; interrupting
        mid-word would be jarring. New voice/rate applies from cur+1 onward.
        """
        if not self.synth:
            return
        from_idx = self.current_idx + 1
        if from_idx >= len(self.sentences):
            return
        await self.synth.cancel()
        self.synth.cleanup()
        self.synth = Synth(
            self.sentences, self.voice, self.rate, make_aligner(self.align_name)
        )
        # Re-attach widgets to the new synth's empty timings; they'll repopulate.
        for i in range(from_idx, len(self.sentences)):
            self.sentence_widgets[i].set_timings([])
        self.synth.start(from_idx)
        if self._ready_task and not self._ready_task.done():
            self._ready_task.cancel()
        self._ready_task = asyncio.create_task(self._consume_ready())

    async def action_quit(self) -> None:
        self.exit()

    async def action_new_text(self) -> None:
        """Exit ReciteApp with a sentinel so main() loops back to PasteApp."""
        self.exit("paste")

    async def action_show_help(self) -> None:
        # App-level priority bindings fire even when a ModalScreen is on top,
        # so this same `?` action handles both opening and closing the modal.
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            await self.push_screen(HelpScreen())

    def action_panic_exit(self) -> None:
        """Hard exit that bypasses Textual's shutdown sequence.
        Use when the normal `q` quit is wedged (event loop blocked, child
        process stuck, etc.). Best-effort restores the terminal then calls
        os._exit, so afplay/say children may be orphaned — `pkill -9 afplay`
        afterwards if you still hear audio."""
        try:
            subprocess.run(["stty", "sane"], check=False, timeout=1)
        except Exception:
            pass
        os._exit(130)
