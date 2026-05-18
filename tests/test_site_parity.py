"""Acceptance tests: the running app must match what recite-site claims.

Each test maps to a specific assertion on the marketing site. If a test
fails, either the app diverged from the site or the site overclaimed.
Fix one of the two; never silence the test."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from textual.widgets import Static, TextArea  # noqa: F401  (used by paste helper)

from recite.app import ReciteApp
from recite.paste import PasteApp


def _make_app(
    sentences: list[str] | None = None,
    voice: str = "Daniel",
    rate: int = 200,
    align: str = "heuristic",
) -> ReciteApp:
    return ReciteApp(
        sentences=sentences or ["Hello world.", "Another sentence."],
        voice=voice,
        rate=rate,
        align=align,
    )


def _status_text(app: ReciteApp) -> str:
    """Build the status-line text (pure function, no widget query)."""
    return app._build_status_text()


# ─── A1: elapsed / total time clock in status line ──────────────────────────

@pytest.mark.asyncio
async def test_status_shows_elapsed_and_total_time_during_playback():
    """Site step 04 mockup: `00:14 / 00:38`. App must render MM:SS / MM:SS
    while a sentence is playing."""
    app = _make_app(["Hello world."])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.synth is not None
        track = app.synth.track(0)
        assert track is not None
        track.duration_s = 38.0

        app.is_playing = True
        app.is_paused = False
        app.finished = False

        with patch.object(app.player, "position", return_value=14.0):
            app._refresh_status()
            await pilot.pause()
            status = _status_text(app)

    assert "00:14 / 00:38" in status, (
        f"clock must render `MM:SS / MM:SS` literal per the site mockup: {status!r}"
    )


@pytest.mark.asyncio
async def test_status_time_uses_mm_ss_zero_padded():
    """Site shows `00:14 / 00:38` not `0:14 / 0:38`. Always two-digit MM and SS."""
    app = _make_app(["Hello world."])
    async with app.run_test() as pilot:
        await pilot.pause()
        track = app.synth.track(0)
        track.duration_s = 7.5
        app.is_playing = True

        with patch.object(app.player, "position", return_value=3.0):
            app._refresh_status()
            await pilot.pause()
            status = _status_text(app)

    assert "00:03" in status, f"expected zero-padded MM:SS, got: {status!r}"
    assert "00:07" in status, f"expected zero-padded MM:SS, got: {status!r}"


# ─── A2: queue counter when pending > 0 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_status_shows_queue_when_pending_tracks_remain():
    """Site hero meta: `queue: 1 synthesised · 0 pending`. While synthesis is
    still in flight, surface ready-vs-pending counts."""
    app = _make_app(["s1", "s2", "s3", "s4"])
    async with app.run_test() as pilot:
        await pilot.pause()
        # Force track 0 to look ready, the rest pending. Direct flag-write
        # is fine here because there's no Synth public API to set readiness
        # from the outside; the production code reads via Synth.progress().
        assert app.synth is not None
        for i in range(len(app.sentences)):
            track = app.synth.track(i)
            assert track is not None
            track.ready = (i == 0)

        app._refresh_status()
        await pilot.pause()
        status = _status_text(app)

    assert "1 synthesised" in status, (
        f"expected `1 synthesised` literal in: {status!r}"
    )
    assert "3 pending" in status, (
        f"expected `3 pending` literal in: {status!r}"
    )


@pytest.mark.asyncio
async def test_status_omits_queue_when_everything_is_ready():
    """Site doesn't show the queue line when nothing's pending; only surface
    it while it conveys useful information."""
    app = _make_app(["s1", "s2"])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.synth is not None
        for i in range(len(app.sentences)):
            track = app.synth.track(i)
            assert track is not None
            track.ready = True

        app._refresh_status()
        await pilot.pause()
        status = _status_text(app)

    assert "queue" not in status.lower(), (
        f"queue indicator should be hidden when nothing is pending: {status!r}"
    )


# ─── A5: title bar format must include voice / rate / aligner ───────────────

@pytest.mark.asyncio
async def test_subtitle_includes_voice_rate_and_aligner():
    """Site hero title bar: `recite · daniel @ 200 wpm · aligner: heuristic`.
    The app's `sub_title` must surface all three."""
    app = _make_app(voice="Daniel", rate=200, align="heuristic")
    async with app.run_test() as pilot:
        await pilot.pause()

    # Site hero title bar is `recite · daniel @ 200 wpm · aligner: heuristic`.
    # Assert the literal separators so a bare-concat regression fails loudly.
    sub = app.sub_title
    assert "daniel @ 200 wpm" in sub, (
        f"subtitle must render `<voice> @ <rate> wpm`: {sub!r}"
    )
    assert "aligner: heuristic" in sub, (
        f"subtitle must render `aligner: <align>`: {sub!r}"
    )
    assert " · " in sub, (
        f"subtitle must use the middle-dot separator from the site: {sub!r}"
    )


@pytest.mark.asyncio
async def test_subtitle_shows_default_when_rate_is_zero():
    """When `--rate 0` (system default), the subtitle should say so rather
    than display `0 wpm`."""
    app = _make_app(rate=0)
    async with app.run_test() as pilot:
        await pilot.pause()

    sub = app.sub_title.lower()
    assert "default" in sub or "system" in sub, (
        f"expected 'default'/'system' wording for rate=0, got: {app.sub_title!r}"
    )


# ─── A6: footer must surface voice + rate bindings ──────────────────────────

class TestFooterBindingsParity:
    """Site hero transport bar always shows `v voice` and `+ - rate` keys.
    Textual's Footer only renders bindings with show=True, so those bindings
    must be visible, not hidden behind the `?` help modal."""

    def test_v_cycle_voice_visible_in_footer(self):
        v_bindings = [b for b in ReciteApp.BINDINGS if b.action == "cycle_voice"]
        assert v_bindings, "no cycle_voice binding registered"
        assert v_bindings[0].show is True, (
            "v (cycle voice) must be visible in the footer per the site mockup"
        )

    def test_faster_rate_visible_in_footer(self):
        bindings = [b for b in ReciteApp.BINDINGS if b.action == "faster"]
        assert bindings and bindings[0].show is True, (
            "+ (speak faster) must be visible in the footer per the site mockup"
        )

    def test_slower_rate_visible_in_footer(self):
        bindings = [b for b in ReciteApp.BINDINGS if b.action == "slower"]
        assert bindings and bindings[0].show is True, (
            "- (speak slower) must be visible in the footer per the site mockup"
        )

    def test_footer_does_not_exceed_nine_bindings(self):
        """Bloat-prevention lock: don't accidentally surface more than the
        site advertises (space, j/k, r-replay is hidden, ctrl+n, ?, q, v, +, -)."""
        visible = [b for b in ReciteApp.BINDINGS if b.show]
        assert len(visible) <= 9, (
            f"footer over-bloated: {[b.action for b in visible]}"
        )


@pytest.mark.asyncio
async def test_footer_renders_quit_at_80_cols():
    """Counting visible bindings is necessary but not sufficient. Textual's
    Footer docks the command-palette hint on the right and z-orders it over
    any binding that would render in the gutter, so the visible binding count
    can pass while the rightmost labels are silently clipped from the
    rendered output. 80 cols is Terminal.app's default; that's where the
    bug first appears."""
    app = _make_app(["Hello world."])
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        svg = app.export_screenshot()

    assert "quit" in svg, (
        "the `q quit` binding is missing from the rendered footer at 80 cols; "
        "the command-palette hint is probably docking over it"
    )
    assert "voice" in svg, (
        "the `v voice` binding is missing from the rendered footer at 80 cols"
    )


# ─── A3: paste screen char / word / duration counters ───────────────────────

def _hint_text(app: PasteApp) -> str:
    return app._build_hint_text()


@pytest.mark.asyncio
async def test_paste_screen_shows_char_count_live():
    """Step 03 mockup: `847 chars · 142 words · ~38 sec @ 200 wpm`.
    Char count must update as the user types."""
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "Hello world."
        await pilot.pause()
        # Allow live-update hook to fire
        for _ in range(5):
            await pilot.pause()
        hint = _hint_text(app)

    assert "12" in hint, f"expected char count 12 in hint: {hint!r}"
    assert "char" in hint.lower(), f"expected the word 'chars' in hint: {hint!r}"


@pytest.mark.asyncio
async def test_paste_screen_shows_word_count_live():
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "One two three four five."
        await pilot.pause()
        for _ in range(5):
            await pilot.pause()
        hint = _hint_text(app)

    assert "5" in hint, f"expected word count 5 in hint: {hint!r}"
    assert "word" in hint.lower(), f"expected the word 'words' in hint: {hint!r}"


@pytest.mark.asyncio
async def test_paste_screen_shows_estimated_duration_at_200_wpm():
    """Site quotes `~43 sec @ 200 wpm`; the ETA is words / 200 * 60 seconds.
    With 100 words that's 30 sec; assert the readout is roughly right."""
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = " ".join(["word"] * 100)
        await pilot.pause()
        for _ in range(5):
            await pilot.pause()
        hint = _hint_text(app)

    assert "30" in hint, f"expected ~30 sec ETA for 100 words: {hint!r}"
    assert "sec" in hint.lower(), f"expected 'sec' unit in hint: {hint!r}"
    assert "200" in hint, f"expected '200 wpm' marker in hint: {hint!r}"


# ─── A4: paste screen ready indicator toggles with content ──────────────────

@pytest.mark.asyncio
async def test_paste_screen_idle_hint_when_empty():
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        hint = _hint_text(app)

    assert "ready" not in hint.lower(), (
        f"empty TextArea should not show 'ready' indicator: {hint!r}"
    )


@pytest.mark.asyncio
async def test_paste_screen_ready_indicator_appears_when_text_present():
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "Some pasted text."
        await pilot.pause()
        for _ in range(5):
            await pilot.pause()
        hint = _hint_text(app)

    assert "ready" in hint.lower(), (
        f"non-empty TextArea must show 'ready' indicator: {hint!r}"
    )
