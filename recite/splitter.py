"""Sentence splitting with abbreviation handling.

Designed to handle common prose patterns without breaking on titles
(Mr., Dr.), abbreviations (e.g., i.e., etc.), or list-style input.
"""

from __future__ import annotations

import re

_ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr",
        "st", "mt", "rd", "co", "inc", "ltd", "ave",
        "vs", "etc", "eg", "ie", "approx", "fig",
        "vol", "no", "p", "pp", "ch", "ed", "trans",
        "jan", "feb", "mar", "apr", "jun", "jul",
        "aug", "sep", "sept", "oct", "nov", "dec",
        "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    }
)

# A candidate sentence boundary: terminator punctuation followed by whitespace
# and a capital letter (or opening quote/bracket then capital).
_BOUNDARY_RE = re.compile(r"""([.!?]+["')\]]?)\s+(?=["'(\[]?[A-Z0-9])""")
_WS_RE = re.compile(r"\s+")


def split_sentences(text: str) -> list[str]:
    """Chunk text into speakable sentences.

    Splits on hard newlines first so that lists and code-like inputs each
    become their own fragment, then sentence-splits within each fragment.
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = [line.strip() for line in text.split("\n") if line.strip()]
    out: list[str] = []
    for paragraph in paragraphs:
        out.extend(_split_paragraph(paragraph))
    return out


def _split_paragraph(paragraph: str) -> list[str]:
    matches = list(_BOUNDARY_RE.finditer(paragraph))
    if not matches:
        return [_WS_RE.sub(" ", paragraph)]

    out: list[str] = []
    start = 0
    for match in matches:
        punct_end = match.start() + len(_leading_punct(match.group(0)))
        chunk = paragraph[start:punct_end]
        # Detect abbreviation: word immediately before the period.
        trimmed = chunk.rstrip(".!?\"')]")
        word_start = max(trimmed.rfind(" "), trimmed.rfind("\t"), trimmed.rfind("\n")) + 1
        word = trimmed[word_start:].lower()
        if word in _ABBREVIATIONS:
            continue  # not a real sentence boundary
        out.append(_WS_RE.sub(" ", paragraph[start:punct_end]).strip())
        start = match.end()

    tail = _WS_RE.sub(" ", paragraph[start:]).strip()
    if tail:
        out.append(tail)
    return out


def _leading_punct(s: str) -> str:
    """Return the leading run of terminator punctuation from `s`."""
    for i, ch in enumerate(s):
        if ch not in '.!?"\')]':
            return s[:i]
    return s


def tokenise_words(sentence: str) -> list[tuple[int, int, str]]:
    """Return a list of (start_idx, end_idx, word) tuples for a sentence.

    Indices are into the original `sentence` string. Words include the
    apostrophe-suffixed parts (e.g. "don't" is one token).
    """
    tokens: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-]*", sentence):
        tokens.append((match.start(), match.end(), match.group(0)))
    return tokens
