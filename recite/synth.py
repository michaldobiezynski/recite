"""Sentence synthesis pipeline.

Each sentence is independently:
  1. Synthesised by `say -o N.aiff` into a temp directory.
  2. Aligned (heuristic or aeneas) to produce per-word timings.
  3. Marked ready; the app can begin playback as soon as its index is ready.

A background asyncio task processes sentences in order; navigation can race
ahead and request a specific index, which jumps the queue.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .aligners import Aligner, WordTiming, audio_duration_seconds


@dataclass
class Track:
    """The audio + timing pair for one sentence."""

    index: int
    sentence: str
    audio_path: str | None = None
    timings: list[WordTiming] = field(default_factory=list)
    error: Exception | None = None
    ready: bool = False
    duration_s: float = 0.0


class Synth:
    """Background pre-render queue.

    Sentences are pre-synthesised and pre-aligned ahead of playback. Each
    becoming-ready emits an event on `ready_queue` with its index. The app
    listens for the index it cares about (typically the current cursor)
    and begins playback as soon as it arrives.
    """

    def __init__(
        self,
        sentences: list[str],
        voice: str,
        rate: int,
        aligner: Aligner,
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.aligner = aligner
        self._tracks: list[Track] = [Track(i, s) for i, s in enumerate(sentences)]
        self._dir: str = tempfile.mkdtemp(prefix="recite-")
        self._ready: asyncio.Queue[int] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._cancelled = False
        # Handle to the currently-running `say` subprocess so cancel() can kill
        # it. Shared between the worker thread and the event loop; guard with
        # a threading.Lock (not asyncio.Lock; the worker can't await).
        self._current_proc: subprocess.Popen[bytes] | None = None
        self._proc_lock = threading.Lock()

    @property
    def ready_queue(self) -> asyncio.Queue[int]:
        return self._ready

    def track(self, idx: int) -> Track | None:
        if 0 <= idx < len(self._tracks):
            return self._tracks[idx]
        return None

    def start(self, from_idx: int = 0) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._cancelled = False
        self._task = asyncio.create_task(self._run(from_idx))

    async def cancel(self) -> None:
        self._cancelled = True
        # Kill any in-flight `say` so the worker thread's `proc.wait()` returns
        # promptly. Without this, shutdown stalls until `say` finishes the
        # current sentence (multiple seconds for long ones).
        self._kill_current_proc()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    def _kill_current_proc(self) -> None:
        with self._proc_lock:
            proc = self._current_proc
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass

    def cleanup(self) -> None:
        if self._dir and os.path.isdir(self._dir):
            shutil.rmtree(self._dir, ignore_errors=True)

    async def _run(self, from_idx: int) -> None:
        for i in range(from_idx, len(self._tracks)):
            if self._cancelled:
                return
            track = self._tracks[i]
            if track.ready:
                continue
            try:
                await self._render(track)
                track.ready = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                track.error = exc
                track.ready = True
            await self._ready.put(i)

    async def _render(self, track: Track) -> None:
        audio_path = os.path.join(self._dir, f"s{track.index:05d}.aiff")
        args = ["say", "-o", audio_path]
        if self.voice:
            args += ["-v", self.voice]
        if self.rate > 0:
            args += ["-r", str(self.rate)]
        args.append(track.sentence)

        # `say` is synchronous; run in a thread so the event loop keeps going.
        # Use Popen instead of subprocess.run so cancel() can kill it.
        await asyncio.to_thread(self._run_say_blocking, args)

        if self._cancelled:
            return

        if not Path(audio_path).exists():
            raise RuntimeError(f"say produced no audio for sentence {track.index}")

        track.audio_path = audio_path
        track.duration_s = audio_duration_seconds(audio_path)
        track.timings = await self.aligner.align(track.sentence, audio_path)

    def _run_say_blocking(self, args: list[str]) -> None:
        """Spawn `say` and block until it exits. Killable via cancel()."""
        with self._proc_lock:
            if self._cancelled:
                return
            proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._current_proc = proc
        try:
            proc.wait()
        finally:
            with self._proc_lock:
                if self._current_proc is proc:
                    self._current_proc = None


def available_voices() -> list[str]:
    """Return a curated list of voices the user is likely to have."""
    defaults = ["Daniel", "Samantha", "Karen", "Moira", "Tessa", "Alex", "Fiona"]
    try:
        out = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return defaults
    installed: set[str] = set()
    for line in out.stdout.splitlines():
        # "Daniel              en_GB    # ..."
        parts = line.split()
        if parts:
            installed.add(parts[0])
    available = [v for v in defaults if v in installed]
    return available or defaults
