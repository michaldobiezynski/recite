"""Unit tests for `reflow_terminal_wraps` and its end-to-end composition
with the sentence splitter (which is the user-audible contract)."""

import pytest

from recite.normalise import reflow_terminal_wraps
from recite.splitter import split_sentences


class TestReflowTerminalWraps:
    def test_empty_returns_empty(self):
        assert reflow_terminal_wraps("") == ""

    def test_whitespace_only_returns_empty(self):
        assert reflow_terminal_wraps("   \n\t  ") == ""

    def test_single_line_unchanged(self):
        assert reflow_terminal_wraps("hello world.") == "hello world."

    def test_two_line_wrap_reflows_to_one(self):
        wrapped = "Move audio to external SSD. Do not\nauto-delete; verify."
        assert (
            reflow_terminal_wraps(wrapped)
            == "Move audio to external SSD. Do not auto-delete; verify."
        )

    def test_blank_line_preserved_as_paragraph_break(self):
        text = "First paragraph.\n\nSecond paragraph."
        assert reflow_terminal_wraps(text) == "First paragraph.\n\nSecond paragraph."

    def test_multiple_blank_lines_collapse_to_one_break(self):
        text = "First.\n\n\n\nSecond."
        assert reflow_terminal_wraps(text) == "First.\n\nSecond."

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("- one\n- two\n- three", "- one\n\n- two\n\n- three"),
            ("* one\n* two", "* one\n\n* two"),
            ("• one\n• two", "• one\n\n• two"),
            ("1. one\n2. two\n3. three", "1. one\n\n2. two\n\n3. three"),
            ("1) one\n2) two", "1) one\n\n2) two"),
        ],
        ids=["dash", "asterisk", "unicode-bullet", "numbered-dot", "numbered-paren"],
    )
    def test_list_markers_preserved_as_separate_fragments(self, raw, expected):
        assert reflow_terminal_wraps(raw) == expected

    def test_markdown_heading_preserved(self):
        text = "# Title\nbody text that\nwraps onto two lines."
        assert (
            reflow_terminal_wraps(text)
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
        assert reflow_terminal_wraps(text) == expected

    def test_trailing_blank_lines_stripped(self):
        assert reflow_terminal_wraps("Hello.\n\n\n") == "Hello."

    def test_leading_blank_lines_stripped(self):
        assert reflow_terminal_wraps("\n\nHello.") == "Hello."

    def test_already_clean_text_unchanged(self):
        text = "A single line of prose with no funny stuff."
        assert reflow_terminal_wraps(text) == text

    def test_crlf_line_endings_normalised(self):
        # Windows clipboards deliver `\r\n`. The `\r` is dropped by per-line
        # `strip()` so reflow works incidentally. Lock that in.
        assert reflow_terminal_wraps("a\r\nb") == "a b"

    def test_negative_number_not_treated_as_bullet(self):
        # `-1.` is digit-after-dash, not a list marker; the regex requires
        # whitespace after the marker. Lock in the prose interpretation.
        text = "-1. degrees Celsius is cold.\n-2. continues here"
        assert (
            reflow_terminal_wraps(text)
            == "-1. degrees Celsius is cold. -2. continues here"
        )

    def test_hash_without_space_is_not_a_heading(self):
        # CommonMark spec 4.2 requires whitespace after the `#` sequence.
        # `#Tag` is prose; the regex matches the spec. Lock it in.
        assert reflow_terminal_wraps("#Tag\nbody") == "#Tag body"

    def test_idempotent_on_already_reflowed_input(self):
        # Applying reflow twice must produce the same result, because the
        # paste path and the main path both call it on overlapping text.
        text = "first paragraph that\nwraps.\n\n- a\n- b"
        once = reflow_terminal_wraps(text)
        assert reflow_terminal_wraps(once) == once


class TestReflowComposedWithSplitter:
    """End-to-end: prove the bug is fixed for the user. The splitter sees
    the reflowed text and produces complete sentences, not fragments."""

    def test_terminal_wrapped_paragraph_splits_into_full_sentences(self):
        wrapped = (
            "Move audio to an external SSD via symlink during Phase 0. Do not\n"
            "auto-delete; verification of citations does not need local audio.\n"
            "Confidence: High."
        )
        sentences = split_sentences(reflow_terminal_wraps(wrapped))
        assert sentences == [
            "Move audio to an external SSD via symlink during Phase 0.",
            (
                "Do not auto-delete; verification of citations does not need "
                "local audio."
            ),
            "Confidence: High.",
        ]

    def test_mixed_prose_and_list_yields_correct_fragment_order(self):
        text = (
            "Intro that wraps\nacross two lines.\n"
            "\n"
            "- first item\n- second item\n"
            "\n"
            "Closing sentence."
        )
        assert split_sentences(reflow_terminal_wraps(text)) == [
            "Intro that wraps across two lines.",
            "- first item",
            "- second item",
            "Closing sentence.",
        ]

    def test_heading_then_wrapped_body(self):
        text = "# Disk policy\nMove audio to an SSD. Do not\nauto-delete."
        assert split_sentences(reflow_terminal_wraps(text)) == [
            "# Disk policy",
            "Move audio to an SSD.",
            "Do not auto-delete.",
        ]
