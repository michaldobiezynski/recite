"""Pilot-based behavioural tests for the paste-text App."""

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
