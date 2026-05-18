"""Unit tests for the pure-logic parts of the aligners module.

Full alignment end-to-end requires a real audio file synthesised by `say`,
so it is left to integration testing.
"""

from unittest.mock import MagicMock, patch

import pytest

from recite.aligners import (
    HeuristicAligner,
    audio_duration_seconds,
    make_aligner,
)


class TestHeuristicAlignerWeight:
    def test_base_weight_equals_word_length(self):
        assert HeuristicAligner._weight("hello", 0, 5) == 5.0

    def test_trailing_comma_adds_one_point_five(self):
        # Sentence: "hello,"; word is "hello" (0..5), trailing char is ','.
        assert HeuristicAligner._weight("hello,", 0, 5) == 5.0 + 1.5

    def test_trailing_semicolon_adds_one_point_five(self):
        assert HeuristicAligner._weight("hello;", 0, 5) == 5.0 + 1.5

    def test_trailing_period_adds_three(self):
        assert HeuristicAligner._weight("hello.", 0, 5) == 5.0 + 3.0

    def test_trailing_question_mark_adds_three(self):
        assert HeuristicAligner._weight("hello?", 0, 5) == 5.0 + 3.0

    def test_trailing_exclamation_adds_three(self):
        assert HeuristicAligner._weight("hello!", 0, 5) == 5.0 + 3.0

    def test_trailing_colon_adds_one(self):
        assert HeuristicAligner._weight("hello:", 0, 5) == 5.0 + 1.0

    def test_no_trailing_char_no_bonus(self):
        # The word "world" lives at offset 6..11 in "hello world" and has
        # no character after it.
        assert HeuristicAligner._weight("hello world", 6, 11) == 5.0

    def test_trailing_alphanumeric_gives_no_bonus(self):
        # The bonus is only for punctuation, not for any character.
        assert HeuristicAligner._weight("ab c", 0, 2) == 2.0


class TestAudioDurationSeconds:
    def test_parses_estimated_duration_line(self):
        fake = MagicMock(
            stdout=(
                "File:             /tmp/foo.aiff\n"
                "File type ID:     AIFF\n"
                "estimated duration: 1.234567 sec\n"
                "audio bytes:      12345\n"
            )
        )
        with patch("recite.aligners.subprocess.run", return_value=fake):
            assert audio_duration_seconds("dummy.aiff") == pytest.approx(1.234567)

    def test_returns_zero_when_no_duration_in_output(self):
        fake = MagicMock(stdout="some unrelated output\n")
        with patch("recite.aligners.subprocess.run", return_value=fake):
            assert audio_duration_seconds("dummy.aiff") == 0.0

    def test_returns_zero_when_output_is_empty(self):
        fake = MagicMock(stdout="")
        with patch("recite.aligners.subprocess.run", return_value=fake):
            assert audio_duration_seconds("dummy.aiff") == 0.0


class TestMakeAligner:
    def test_heuristic_aligner_constructs(self):
        aligner = make_aligner("heuristic")
        assert isinstance(aligner, HeuristicAligner)

    def test_case_insensitive(self):
        aligner = make_aligner("HEURISTIC")
        assert isinstance(aligner, HeuristicAligner)

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="unknown aligner"):
            make_aligner("not-a-real-aligner")

    def test_aeneas_without_install_raises_runtime_error(self):
        # When the aeneas package is not installed, AeneasAligner.__init__
        # converts the ImportError into a RuntimeError with an install hint.
        try:
            import aeneas  # noqa: F401
            pytest.skip("aeneas is installed; missing-import path cannot be tested")
        except ImportError:
            pass
        with pytest.raises(RuntimeError, match="aeneas is not installed"):
            make_aligner("aeneas")


class TestHeuristicAlignerAlign:
    """End-to-end tests for HeuristicAligner.align with audio_duration mocked.

    These pin behaviour that the per-call _weight unit tests alone cannot
    catch: leading and trailing silence insets, contiguous coverage of the
    speakable interval, and the empty-input short-circuits.
    """

    async def test_two_word_sentence_distributes_speakable_duration(self):
        aligner = HeuristicAligner()
        with patch("recite.aligners.audio_duration_seconds", return_value=1.0):
            timings = await aligner.align("hello world", "/fake.aiff")

        assert [t.word for t in timings] == ["hello", "world"]
        # Leading silence inset on the first word's start.
        assert timings[0].start_s == pytest.approx(HeuristicAligner.LEADING_SILENCE)
        # Trailing silence inset before the last word's end.
        assert timings[-1].end_s == pytest.approx(
            1.0 - HeuristicAligner.TRAILING_SILENCE
        )
        # No gaps between consecutive words.
        for prev, curr in zip(timings, timings[1:]):
            assert prev.end_s == pytest.approx(curr.start_s)

    async def test_empty_sentence_returns_no_timings(self):
        aligner = HeuristicAligner()
        # Early-return path should not even call audio_duration_seconds.
        with patch("recite.aligners.audio_duration_seconds") as mock_dur:
            timings = await aligner.align("", "/fake.aiff")
        assert timings == []
        mock_dur.assert_not_called()

    async def test_zero_duration_returns_no_timings(self):
        aligner = HeuristicAligner()
        with patch("recite.aligners.audio_duration_seconds", return_value=0.0):
            timings = await aligner.align("hello world", "/fake.aiff")
        assert timings == []
