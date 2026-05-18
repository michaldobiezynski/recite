"""Pilot-based behavioural tests for the main player App's bindings.

These exercise the *binding wiring* — that the right action runs for the
right key — not the audio pipeline. Audio synthesis requires `say` which
is macOS-only and slow, so it's left to integration testing.
"""

import pytest

from recite.app import HelpScreen, ReciteApp


def _make_app() -> ReciteApp:
    return ReciteApp(
        sentences=["Hello world."],
        voice="Daniel",
        rate=0,
        align="heuristic",
    )


@pytest.mark.asyncio
async def test_q_quits_with_none():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        for _ in range(30):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value is None


@pytest.mark.asyncio
async def test_escape_quits_with_none():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        for _ in range(30):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value is None


@pytest.mark.asyncio
async def test_ctrl_n_exits_with_paste_sentinel():
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+n")
        for _ in range(30):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value == "paste"


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_help_modal_does_not_stack_on_repeated_open():
    # Regression test for the App-level priority binding gotcha that pushed
    # a fresh HelpScreen on every `?` instead of dismissing the existing one.
    app = _make_app()
    async with app.run_test() as pilot:
        await pilot.pause()
        for _ in range(4):
            await pilot.press("question_mark")
            await pilot.pause()
        # Four presses -> open, close, open, close.
        assert not isinstance(app.screen, HelpScreen)


class TestFooterBindings:
    """Cosmetic invariants we want to lock in to keep the footer slim on
    narrow terminals. If you add a binding, decide explicitly whether it's
    visible or hidden — don't accidentally bloat the footer."""

    def test_quit_binding_is_priority(self):
        quit_bindings = [b for b in ReciteApp.BINDINGS if "quit" in b.action]
        assert quit_bindings and all(b.priority for b in quit_bindings)

    def test_panic_exit_is_hidden_priority(self):
        panic = [b for b in ReciteApp.BINDINGS if b.action == "panic_exit"]
        assert panic and panic[0].priority
        assert panic[0].show is False
