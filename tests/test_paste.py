"""Pilot-based behavioural tests for the paste-text App."""

import pytest
from textual.widgets import TextArea

from recite.paste import PasteApp, reflow_paste_text


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
    """Acceptance test for the bug: text copied from Claude Code (or any
    terminal that hard-wraps at column 80) preserves those newlines on
    paste. Without reflow each wrapped line becomes its own fragment in
    recite and sentences play in pieces. Submitting must collapse the
    soft wraps so a paragraph travels intact to the splitter."""
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


class TestReflowPasteText:
    """Unit tests covering the reflow rules. The function lives in paste
    because that is the only entry point that opts in; stdin and file
    inputs deliberately keep their existing behaviour."""

    def test_empty_returns_empty(self):
        assert reflow_paste_text("") == ""

    def test_whitespace_only_returns_empty(self):
        assert reflow_paste_text("   \n\t  ") == ""

    def test_single_line_unchanged(self):
        assert reflow_paste_text("hello world.") == "hello world."

    def test_two_line_wrap_reflows_to_one(self):
        wrapped = "Move audio to external SSD. Do not\nauto-delete; verify."
        assert (
            reflow_paste_text(wrapped)
            == "Move audio to external SSD. Do not auto-delete; verify."
        )

    def test_blank_line_preserved_as_paragraph_break(self):
        text = "First paragraph.\n\nSecond paragraph."
        assert reflow_paste_text(text) == "First paragraph.\n\nSecond paragraph."

    def test_multiple_blank_lines_collapse_to_one_break(self):
        text = "First.\n\n\n\nSecond."
        assert reflow_paste_text(text) == "First.\n\nSecond."

    def test_bullet_list_items_preserved_as_separate_fragments(self):
        text = "- one\n- two\n- three"
        assert reflow_paste_text(text) == "- one\n\n- two\n\n- three"

    def test_asterisk_bullet_list_preserved(self):
        text = "* one\n* two"
        assert reflow_paste_text(text) == "* one\n\n* two"

    def test_unicode_bullet_list_preserved(self):
        text = "• one\n• two"
        assert reflow_paste_text(text) == "• one\n\n• two"

    def test_numbered_list_preserved(self):
        text = "1. one\n2. two\n3. three"
        assert reflow_paste_text(text) == "1. one\n\n2. two\n\n3. three"

    def test_numbered_list_paren_style_preserved(self):
        text = "1) one\n2) two"
        assert reflow_paste_text(text) == "1) one\n\n2) two"

    def test_markdown_heading_preserved(self):
        text = "# Title\nbody text that\nwraps onto two lines."
        assert (
            reflow_paste_text(text)
            == "# Title\n\nbody text that wraps onto two lines."
        )

    def test_mixed_prose_list_prose(self):
        text = (
            "Intro paragraph that\nwraps across lines.\n"
            "\n"
            "- item one\n- item two\n"
            "\n"
            "Closing prose."
        )
        expected = (
            "Intro paragraph that wraps across lines.\n\n"
            "- item one\n\n- item two\n\n"
            "Closing prose."
        )
        assert reflow_paste_text(text) == expected

    def test_trailing_blank_lines_stripped(self):
        text = "Hello.\n\n\n"
        assert reflow_paste_text(text) == "Hello."

    def test_leading_blank_lines_stripped(self):
        text = "\n\nHello."
        assert reflow_paste_text(text) == "Hello."

    def test_already_clean_text_unchanged(self):
        # Single paragraph with no wraps, no lists: passes through.
        text = "A single line of prose with no funny stuff."
        assert reflow_paste_text(text) == text
