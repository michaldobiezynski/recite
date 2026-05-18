"""Pilot-based behavioural tests for the main player App's bindings.

These exercise the binding wiring (that the right action runs for the right
key), not the audio pipeline. Audio synthesis requires `say`, which is
macOS-only and slow, so it is left to integration testing.
"""

from textual.widgets import Static

from recite.aligners import WordTiming
from recite.app import HelpScreen, ReciteApp


def _make_app() -> ReciteApp:
    return ReciteApp(
        sentences=["Hello world."],
        voice="Daniel",
        rate=0,
        align="heuristic",
    )


async def test_q_quits_with_none(wait_for_exit):
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await wait_for_exit(app, pilot)
    assert app.return_value is None


async def test_escape_quits_with_none(wait_for_exit):
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await wait_for_exit(app, pilot)
    assert app.return_value is None


async def test_ctrl_n_exits_with_paste_sentinel(wait_for_exit):
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+n")
        await wait_for_exit(app, pilot)
    assert app.return_value == "paste"


async def test_question_mark_toggles_help_modal():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)

        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("question_mark")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


async def test_help_modal_does_not_stack_on_repeated_open():
    # Regression test for the App-level priority binding gotcha that pushed
    # a fresh HelpScreen on every `?` instead of dismissing the existing one.
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(4):
            await pilot.press("question_mark")
            await pilot.pause()
        # Four presses: open, close, open, close.
        assert not isinstance(app.screen, HelpScreen)


async def test_help_modal_lists_major_bindings():
    # Catches the regression of HelpScreen.compose being emptied; a future
    # change that drops a key from the help body should fail loudly.
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        rendered = str(app.screen.query_one("#help-box", Static).render())
    for needle in ("play / pause", "next sentence", "new text", "panic exit"):
        assert needle in rendered, f"help modal missing: {needle!r}"


class TestFooterBindings:
    """Cosmetic invariants that keep the footer slim on narrow terminals."""

    def test_visible_footer_actions_are_locked(self):
        # Naming the actions (not just the count) so a regression diff shows
        # which binding became visible or hidden.
        visible = [b.action for b in ReciteApp.BINDINGS if b.show]
        assert visible == [
            "play_pause",
            "next",
            "prev",
            "new_text",
            "show_help",
            "quit",
        ]

    def test_quit_binding_is_priority(self):
        quit_bindings = [b for b in ReciteApp.BINDINGS if "quit" in b.action]
        assert quit_bindings and all(b.priority for b in quit_bindings)

    def test_panic_exit_is_hidden_priority(self):
        panic = [b for b in ReciteApp.BINDINGS if b.action == "panic_exit"]
        assert panic and panic[0].priority
        assert panic[0].show is False


class TestWordAt:
    """Direct tests for the binary-search routine that drives the per-word
    highlight. Mutation testing flagged this as silently regressable; a
    `return 0` body would pass every other test in the suite."""

    @staticmethod
    def _t(start: float) -> WordTiming:
        return WordTiming(
            word="x", start_idx=0, end_idx=1, start_s=start, end_s=start + 0.1,
        )

    def test_empty_timings_return_minus_one(self):
        assert ReciteApp._word_at([], 0.5) == -1

    def test_position_before_first_start_is_clamped_to_zero(self):
        timings = [self._t(0.5)]
        assert ReciteApp._word_at(timings, 0.0) == 0

    def test_position_at_first_start_returns_zero(self):
        timings = [self._t(0.0), self._t(0.5)]
        assert ReciteApp._word_at(timings, 0.0) == 0

    def test_position_inside_first_interval_returns_zero(self):
        timings = [self._t(0.0), self._t(0.5), self._t(1.0)]
        assert ReciteApp._word_at(timings, 0.3) == 0

    def test_position_inside_second_interval_returns_one(self):
        timings = [self._t(0.0), self._t(0.5), self._t(1.0)]
        assert ReciteApp._word_at(timings, 0.7) == 1

    def test_position_exactly_at_second_start_returns_second(self):
        timings = [self._t(0.0), self._t(0.5)]
        assert ReciteApp._word_at(timings, 0.5) == 1

    def test_position_past_last_returns_last_index(self):
        timings = [self._t(0.0), self._t(0.5)]
        assert ReciteApp._word_at(timings, 10.0) == 1
