"""Pilot-based behavioural tests for the paste-text App.

Unit tests for the reflow function itself live in `test_normalise.py`;
this file focuses on the App wire-up: bindings, exit values, and the
end-to-end reflow-on-submit guarantee from the user's perspective."""

import pytest
from textual.widgets import TextArea

from recite.paste import PasteApp


@pytest.mark.asyncio
async def test_ctrl_s_returns_typed_text():
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "Hello, world."
        await pilot.pause()
        await pilot.press("ctrl+s")
        for _ in range(20):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value == "Hello, world."


@pytest.mark.asyncio
async def test_f5_returns_typed_text():
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "Another sentence."
        await pilot.pause()
        await pilot.press("f5")
        for _ in range(20):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value == "Another sentence."


@pytest.mark.asyncio
async def test_escape_returns_none():
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        for _ in range(20):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value is None


@pytest.mark.asyncio
async def test_empty_then_ctrl_s_returns_none():
    # Submitting an empty TextArea is treated as a cancellation; the main
    # loop interprets None as "no input, exit".
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        for _ in range(20):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value is None


@pytest.mark.asyncio
async def test_whitespace_only_treated_as_empty():
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "   \n\t  "
        await pilot.pause()
        await pilot.press("ctrl+s")
        for _ in range(20):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value is None


@pytest.mark.asyncio
async def test_terminal_wrapped_prose_reflows_on_submit():
    """Acceptance test: text copied from a terminal program (Claude Code,
    man, less) carries hard `\\n` newlines its renderer inserted at the
    wrap point. Submitting must collapse those so a paragraph travels
    intact to the splitter and plays as whole sentences."""
    wrapped = (
        "Move audio to an external SSD via symlink during Phase 0. Do not\n"
        "auto-delete; verification of citations does not need local audio\n"
        "(YouTube URL with timestamp handles that)."
    )
    expected = (
        "Move audio to an external SSD via symlink during Phase 0. "
        "Do not auto-delete; verification of citations does not need local "
        "audio (YouTube URL with timestamp handles that)."
    )
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = wrapped
        await pilot.pause()
        await pilot.press("ctrl+s")
        for _ in range(20):
            await pilot.pause()
            if not app.is_running:
                break
    assert app.return_value == expected
