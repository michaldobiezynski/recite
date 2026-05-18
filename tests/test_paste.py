"""Pilot-based behavioural tests for the paste-text App."""

from textual.widgets import TextArea

from recite.paste import PasteApp


async def test_ctrl_s_returns_typed_text(wait_for_exit):
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "Hello, world."
        await pilot.pause()
        await pilot.press("ctrl+s")
        await wait_for_exit(app, pilot)
    assert app.return_value == "Hello, world."


async def test_f5_returns_typed_text(wait_for_exit):
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "Another sentence."
        await pilot.pause()
        await pilot.press("f5")
        await wait_for_exit(app, pilot)
    assert app.return_value == "Another sentence."


async def test_escape_returns_none(wait_for_exit):
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await wait_for_exit(app, pilot)
    assert app.return_value is None


async def test_empty_then_ctrl_s_returns_none(wait_for_exit):
    # Submitting an empty TextArea is treated as cancellation; the main
    # loop interprets None as "no input, exit".
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await wait_for_exit(app, pilot)
    assert app.return_value is None


async def test_whitespace_only_treated_as_empty(wait_for_exit):
    app = PasteApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one(TextArea).text = "   \n\t  "
        await pilot.pause()
        await pilot.press("ctrl+s")
        await wait_for_exit(app, pilot)
    assert app.return_value is None
