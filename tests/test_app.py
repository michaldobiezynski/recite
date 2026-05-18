"""Pilot-based behavioural tests for the main player App's bindings.

These exercise the binding wiring (that the right action runs for the right
key), not the audio pipeline. Audio synthesis requires `say`, which is
macOS-only and slow, so it is left to integration testing.
"""

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
