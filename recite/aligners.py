"""Word-timing aligners.

Two implementations behind a common interface:

- `HeuristicAligner`: zero extra dependencies. Distributes the audio duration
  across visible word tokens, weighted by character count plus a small
  punctuation bonus (commas, periods get a small extra slice for pauses).
  Instant, ~80–90% accurate. Default.

- `AeneasAligner`: forced alignment via the `aeneas` package. Requires
  `pip install aeneas` plus system `espeak` and `ffmpeg`. ~99% accurate but
  adds 1–3 seconds of processing per sentence.

Both return a list of (word_text, start_s, end_s) tuples in sentence order.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .splitter import tokenise_words


@dataclass(frozen=True)
class WordTiming:
    word: str
    start_idx: int  # offset into the sentence string
    end_idx: int
    start_s: float
    end_s: float


class Aligner(Protocol):
    async def align(
        self, sentence: str, audio_path: str
    ) -> list[WordTiming]: ...  # pragma: no cover


def audio_duration_seconds(audio_path: str) -> float:
    """Read the duration of an audio file via afinfo (macOS built-in)."""
    out = subprocess.run(
        ["afinfo", audio_path],
        capture_output=True,
        text=True,
        check=False,
    )
    # afinfo prints lines like: "estimated duration: 1.234567 sec"
    match = re.search(r"estimated duration:\s+([0-9.]+)", out.stdout)
    if match:
        return float(match.group(1))
    return 0.0


class HeuristicAligner:
    """Distribute audio duration across visible word tokens.

    Algorithm:
      1. Tokenise the sentence into visible words.
      2. Read total audio duration via `afinfo`.
      3. Assign each word a weight: len(word) + bonus for adjacent punctuation.
      4. Normalise weights, distribute the duration linearly, with the first
         and last words getting a small inset to account for `say`'s silence
         padding (typically ~50–80ms at each end).
    """

    LEADING_SILENCE = 0.06
    TRAILING_SILENCE = 0.08

    async def align(self, sentence: str, audio_path: str) -> list[WordTiming]:
        tokens = tokenise_words(sentence)
        if not tokens:
            return []
        duration = audio_duration_seconds(audio_path)
        if duration <= 0:
            return []

        speakable = max(0.05, duration - self.LEADING_SILENCE - self.TRAILING_SILENCE)
        weights = [self._weight(sentence, start, end) for (start, end, _) in tokens]
        total = sum(weights) or 1.0

        timings: list[WordTiming] = []
        cursor = self.LEADING_SILENCE
        for (start, end, word), weight in zip(tokens, weights, strict=True):
            slice_len = speakable * (weight / total)
            timings.append(
                WordTiming(
                    word=word,
                    start_idx=start,
                    end_idx=end,
                    start_s=cursor,
                    end_s=cursor + slice_len,
                )
            )
            cursor += slice_len
        return timings

    @staticmethod
    def _weight(sentence: str, start: int, end: int) -> float:
        weight = float(end - start)
        # Bonus for trailing punctuation: natural pauses extend the perceived
        # word duration in continuous speech.
        if end < len(sentence):
            after = sentence[end]
            if after == "," or after == ";":
                weight += 1.5
            elif after in ".!?":
                weight += 3.0
            elif after == ":":
                weight += 1.0
        return weight


class AeneasAligner:
    """Forced alignment via the `aeneas` package.

    Requires the `align` optional dependency to be installed:
        pipx install 'git+https://github.com/michaldobiezynski/recite.git[align]'
    plus system tools:
        brew install espeak ffmpeg
    """

    def __init__(self) -> None:
        # Import lazily so importing this module doesn't pull in aeneas.
        try:
            from aeneas.executetask import ExecuteTask  # noqa: F401
            from aeneas.task import Task  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "aeneas is not installed. Install with: "
                "pipx install 'git+https://github.com/michaldobiezynski/recite.git[align]' "
                "after `brew install espeak ffmpeg`."
            ) from exc

    async def align(self, sentence: str, audio_path: str) -> list[WordTiming]:
        # aeneas is synchronous and CPU-bound. Run it in a worker thread so
        # the Textual event loop stays responsive.
        import asyncio

        return await asyncio.to_thread(self._align_sync, sentence, audio_path)

    def _align_sync(self, sentence: str, audio_path: str) -> list[WordTiming]:
        from aeneas.executetask import ExecuteTask
        from aeneas.task import Task

        tokens = tokenise_words(sentence)
        if not tokens:
            return []

        with tempfile.TemporaryDirectory(prefix="recite-align-") as tmpdir:
            text_path = Path(tmpdir) / "words.txt"
            sync_path = Path(tmpdir) / "sync.json"
            # One word per line gives word-level timings.
            text_path.write_text("\n".join(w for _, _, w in tokens), encoding="utf-8")

            config = "task_language=eng|is_text_type=plain|os_task_file_format=json"
            task = Task(config_string=config)
            task.audio_file_path_absolute = os.path.abspath(audio_path)
            task.text_file_path_absolute = str(text_path)
            task.sync_map_file_path_absolute = str(sync_path)
            ExecuteTask(task).execute()
            task.output_sync_map_file()

            data = json.loads(sync_path.read_text(encoding="utf-8"))

        # aeneas output: {"fragments": [{"begin": "0.000", "end": "0.420", "lines": ["Hello"]}, ...]}
        fragments = data.get("fragments", [])
        timings: list[WordTiming] = []
        for (start, end, word), frag in zip(tokens, fragments, strict=False):
            try:
                start_s = float(frag.get("begin", 0))
                end_s = float(frag.get("end", 0))
            except (TypeError, ValueError):
                continue
            timings.append(
                WordTiming(word=word, start_idx=start, end_idx=end, start_s=start_s, end_s=end_s)
            )
        return timings


def make_aligner(name: str) -> Aligner:
    name = name.lower()
    if name == "heuristic":
        return HeuristicAligner()
    if name == "aeneas":
        return AeneasAligner()
    raise ValueError(f"unknown aligner: {name}")
