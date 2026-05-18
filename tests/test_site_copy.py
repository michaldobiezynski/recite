"""Acceptance tests against the site copy itself.

The site lives in a sibling repo: recite-site/src/App.jsx. These tests assert
that the marketing copy doesn't promise things the app can't deliver, and
that internally-inconsistent mockups have been reconciled. If recite-site is
not present locally (CI runs the recite repo alone), the tests are skipped;
the site is a separate deploy target."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SITE_FILE = Path(__file__).resolve().parents[2] / "recite-site" / "src" / "App.jsx"


@pytest.fixture(scope="module")
def site_text() -> str:
    if not _SITE_FILE.exists():
        pytest.skip(f"recite-site not present at {_SITE_FILE}")
    return _SITE_FILE.read_text(encoding="utf-8")


# ─── B1, B2: install commands must use git URL, not PyPI ────────────────────

def test_no_bare_pipx_install_recite(site_text):
    """`pipx install recite` would install Daniel Obraczka's unrelated
    poetry-release tool. Site must use the git URL until we publish to PyPI
    under a unique name."""
    pattern = re.compile(r"pipx install recite(?!\[?[\w\-/])", re.IGNORECASE)
    matches = pattern.findall(site_text)
    assert not matches, (
        "found bare `pipx install recite` in App.jsx; this installs the wrong "
        "package. Use `pipx install git+https://github.com/michaldobiezynski/recite.git`."
    )


def test_install_commands_use_git_url(site_text):
    """Every visible install command in the site should reference the github
    repo, not a PyPI name we don't own."""
    assert "git+https://github.com/michaldobiezynski/recite" in site_text, (
        "site must reference `git+https://github.com/michaldobiezynski/recite` "
        "for install commands"
    )


def test_aeneas_install_uses_git_url(site_text):
    """`pipx install 'recite[align]'` has the same PyPI-name problem."""
    bad = re.search(r"pipx install ['\"]recite\[align\]['\"]", site_text)
    assert not bad, (
        "aeneas install must use `pipx install "
        "'git+https://github.com/michaldobiezynski/recite.git[align]'`"
    )


# ─── B3: drop the misleading "600 lines" figure ─────────────────────────────

def test_does_not_claim_600_lines(site_text):
    """`wc -l recite/*.py` is ~1300. Either update the figure or omit it."""
    assert "600 lines" not in site_text, (
        "site says 'roughly 600 lines of Python' but actual is ~1,400; "
        "either update the figure or drop the line-count claim"
    )


# ─── B4: paste-screen mockup numbers must reconcile internally ──────────────

def test_paste_mockup_word_count_and_duration_are_consistent(site_text):
    """Step 03 mockup says `142 words · ~38 sec @ 200 wpm`. At 200 wpm,
    142 words = 142/200 * 60 = ~42.6 sec, not 38. Pick consistent numbers."""
    # Pull all `N words · ~M sec @ K wpm` triples from the file and verify
    # each one balances within ±10 % tolerance.
    triples = re.findall(
        r"(\d+)\s+words\s*[·.]\s*~?(\d+)\s*sec\s*@\s*(\d+)\s*wpm",
        site_text,
    )
    assert triples, "expected a `N words · ~M sec @ K wpm` mockup line"
    for words_s, secs_s, wpm_s in triples:
        words, secs, wpm = int(words_s), int(secs_s), int(wpm_s)
        expected = words / wpm * 60
        ratio = secs / expected
        assert 0.9 <= ratio <= 1.1, (
            f"mockup numbers don't reconcile: {words} words at {wpm} wpm "
            f"should be ~{expected:.1f} sec, not {secs}"
        )
