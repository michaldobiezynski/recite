"""Unit tests for the sentence splitter and word tokeniser."""

from recite.splitter import split_sentences, tokenise_words


class TestSplitSentences:
    def test_empty_string_returns_empty_list(self):
        assert split_sentences("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert split_sentences("   \n  \t  ") == []

    def test_single_sentence_no_terminator(self):
        assert split_sentences("hello world") == ["hello world"]

    def test_two_sentences_separated_by_period(self):
        assert split_sentences("Hello world. How are you?") == [
            "Hello world.",
            "How are you?",
        ]

    def test_splits_on_question_mark(self):
        assert split_sentences("Is it ready? Yes.") == ["Is it ready?", "Yes."]

    def test_splits_on_exclamation(self):
        assert split_sentences("Wow! That's amazing.") == [
            "Wow!",
            "That's amazing.",
        ]

    def test_does_not_split_on_dr_abbreviation(self):
        result = split_sentences("I saw Dr. Smith yesterday. He is well.")
        assert result == ["I saw Dr. Smith yesterday.", "He is well."]

    def test_does_not_split_on_mr_abbreviation(self):
        result = split_sentences("Mr. Smith arrived. He greeted us.")
        assert result == ["Mr. Smith arrived.", "He greeted us."]

    def test_does_not_split_on_etc(self):
        assert split_sentences("Cats, dogs, etc. They are pets.") == [
            "Cats, dogs, etc. They are pets.",
        ]

    def test_does_not_split_on_ie(self):
        assert split_sentences(
            "Some animals, i.e. cats, are nocturnal. They hunt at night."
        ) == [
            "Some animals, i.e. cats, are nocturnal.",
            "They hunt at night.",
        ]

    def test_paragraph_breaks_create_boundaries(self):
        assert split_sentences("First line\nSecond line") == [
            "First line",
            "Second line",
        ]

    def test_collapses_internal_whitespace(self):
        # Runs of whitespace within a sentence are normalised to a single space.
        assert split_sentences("hello    world") == ["hello world"]
        assert split_sentences("foo\tbar") == ["foo bar"]

    def test_period_followed_by_lowercase_is_not_a_boundary(self):
        # A documented design choice: the splitter only treats a period as a
        # sentence boundary when the next word starts with a capital letter,
        # digit, or an opening quote/bracket. Lowercase continuations get
        # glued to the previous sentence.
        assert split_sentences("hello world. foo bar") == ["hello world. foo bar"]
        assert split_sentences("Hello world. Foo bar") == ["Hello world.", "Foo bar"]

    def test_handles_quotes_at_sentence_boundary(self):
        result = split_sentences('She said "yes." Then she left.')
        assert result == ['She said "yes."', "Then she left."]

    def test_multiple_terminators_kept_together(self):
        # "Really?!" should be one chunk, not split between ? and !.
        result = split_sentences("Really?! Yes.")
        assert result == ["Really?!", "Yes."]

    def test_strips_outer_whitespace(self):
        assert split_sentences("   hello.   ") == ["hello."]


class TestTokeniseWords:
    def test_empty_string_returns_empty(self):
        assert tokenise_words("") == []

    def test_single_word_returns_one_token(self):
        assert tokenise_words("hello") == [(0, 5, "hello")]

    def test_multiple_words_have_correct_offsets(self):
        assert tokenise_words("hello world") == [
            (0, 5, "hello"),
            (6, 11, "world"),
        ]

    def test_apostrophe_kept_within_word(self):
        assert tokenise_words("don't") == [(0, 5, "don't")]

    def test_hyphen_kept_within_word(self):
        assert tokenise_words("co-author") == [(0, 9, "co-author")]

    def test_punctuation_excluded_from_tokens(self):
        words = [w for _, _, w in tokenise_words("hello, world!")]
        assert words == ["hello", "world"]

    def test_numbers_are_tokens(self):
        words = [w for _, _, w in tokenise_words("year 2026")]
        assert words == ["year", "2026"]

    def test_offsets_index_original_string(self):
        sentence = "Quick brown fox"
        tokens = tokenise_words(sentence)
        for start, end, word in tokens:
            assert sentence[start:end] == word
