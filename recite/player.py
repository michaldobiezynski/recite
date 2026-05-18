"""Audio playback via `afplay` with SIGSTOP/SIGCONT pause.

Exposes a `position()` method that returns elapsed audible time (excluding
pause time) so the UI can drive a word-level highlight.
"""

from __future__ import annotations

import asyncio
import signal
import subprocess
import time
from dataclasses import dataclass


@dataclass
class PlayerEvent:
    index: int
    error: Exception | None = None


class Player:
    """Foreground audio player for a single sentence at a time.

    Pause is implemented with SIGSTOP/SIGCONT on the afplay process. afplay
    has no native pause; signals are the only practical primitive.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._idx: int = -1
        self._started_at: float = 0.0
        self._paused_at: float = 0.0
        self._pause_acc: float = 0.0
        self._paused: bool = False
        self._intentional_stop: bool = False
        self._lock = asyncio.Lock()
        self._events: asyncio.Queue[PlayerEvent] = asyncio.Queue()
        self._watch_task: asyncio.Task[None] | None = None

    @property
    def events(self) -> asyncio.Queue[PlayerEvent]:
        return self._events

    async def play(self, idx: int, path: str) -> None:
        """Begin playback of `path`. Any in-flight playback is cancelled first."""
        await self.stop()
        async with self._lock:
            try:
                proc = subprocess.Popen(
                    ["afplay", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError as exc:
                await self._events.put(PlayerEvent(idx, exc))
                return
            self._proc = proc
            self._idx = idx
            self._started_at = time.monotonic()
            self._pause_acc = 0.0
            self._paused = False
            self._intentional_stop = False
            self._watch_task = asyncio.create_task(self._watch(proc, idx))

    async def _watch(self, proc: subprocess.Popen[bytes], idx: int) -> None:
        """Await process exit and emit a completion event for natural endings."""
        # Poll instead of using asyncio.subprocess so SIGSTOP-paused children
        # don't confuse the event loop's child reaper.
        while True:
            rc = proc.poll()
            if rc is not None:
                break
            await asyncio.sleep(0.05)

        async with self._lock:
            # Only clear if we are still the active player (a newer play() may
            # have replaced us via stop()→play()).
            if self._proc is proc:
                self._proc = None
                self._paused = False
            intentional = self._intentional_stop
            self._intentional_stop = False

        if intentional:
            return
        await self._events.put(PlayerEvent(idx, error=None))

    async def pause(self) -> None:
        async with self._lock:
            if not self._proc or self._paused:
                return
            try:
                self._proc.send_signal(signal.SIGSTOP)
                self._paused = True
                self._paused_at = time.monotonic()
            except ProcessLookupError:
                pass

    async def resume(self) -> None:
        async with self._lock:
            if not self._proc or not self._paused:
                return
            try:
                self._proc.send_signal(signal.SIGCONT)
                self._pause_acc += time.monotonic() - self._paused_at
                self._paused = False
            except ProcessLookupError:
                pass

    async def toggle(self) -> None:
        if self.is_paused:
            await self.resume()
        else:
            await self.pause()

    async def stop(self) -> None:
        async with self._lock:
            proc = self._proc
            self._proc = None
            self._paused = False
            self._intentional_stop = proc is not None
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        if self._watch_task and not self._watch_task.done():
            try:
                await asyncio.wait_for(self._watch_task, timeout=0.5)
            except asyncio.TimeoutError:
                pass

    def position(self) -> float:
        """Audible seconds elapsed for the current sentence (excludes pause time)."""
        if not self._proc:
            return 0.0
        if self._paused:
            return max(0.0, self._paused_at - self._started_at - self._pause_acc)
        return max(0.0, time.monotonic() - self._started_at - self._pause_acc)

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_active(self) -> bool:
        return self._proc is not None

    @property
    def current_index(self) -> int:
        return self._idx
