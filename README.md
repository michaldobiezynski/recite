# recite

A TUI text-to-speech player for the macOS terminal. Built on `say` and `afplay` with **word-level highlighting**: no API keys, no network, no subscription.

Pipe text in, paste from the clipboard, or pass a file. recite splits it into sentences, pre-renders each one to audio, runs alignment to derive word-by-word timings, and plays it back with karaoke-style highlighting and proper transport controls.

## Install

Requires macOS and Python 3.10+. Recommend installing with [pipx](https://pipx.pypa.io/):

```bash
brew install pipx
git clone https://github.com/michaldobiezynski/recite.git
cd recite
make install            # → ~/.local/bin/recite
```

This installs with the **heuristic aligner** (zero extra deps, instant, ~85% accurate). For karaoke-grade accuracy:

```bash
brew install espeak ffmpeg
make install-align      # adds the `aeneas` forced aligner
```

Then run with `recite --align aeneas` to use it.

## Usage

```bash
recite                       # read from clipboard
recite path/to/file.md       # read from a file
cat README.md | recite       # read from stdin
```

Options:

```
--voice NAME       voice to use (default: Daniel)
--rate WPM         speech rate (e.g. 200); 0 = system default
--align heuristic  word-timing aligner (heuristic | aeneas)
```

## Keys

| Key | Action |
| --- | --- |
| `space` | play / pause |
| `j` `→` `n` | next sentence |
| `k` `←` `p` | previous sentence |
| `r` | replay current |
| `g` | jump to start |
| `G` | jump to end |
| `+` | speak faster (+20 wpm) |
| `-` | speak slower (-20 wpm) |
| `v` | cycle voice |
| `q` `esc` | quit |

Voice and rate changes apply from the next sentence onward; the current sentence finishes with its existing rendering rather than cutting off mid-word.

## How it works

```
input → split_sentences → Synth queue → ┐
                                        ├ say -o N.aiff → Aligner → ready
                                        ┘                              │
                                                                       ▼
                              Player (afplay) ◄── pending_play[idx]
                                  │
                                  └─ position() drives word highlight ─► Textual UI
```

- Sentences are pre-rendered ahead of playback in a background asyncio task.
- Each sentence is run through an aligner to produce per-word timings.
- During playback, a 30 ms ticker reads `player.position()` and binary-searches the timing array to find which word is being spoken right now, then re-styles that word in Rich text.
- Pause is `SIGSTOP` on the `afplay` subprocess; resume is `SIGCONT`. The position tracker pauses too, so the highlight freezes correctly.

### Aligners

- **`heuristic`**: distributes the audio duration (from `afinfo`) across visible word tokens, weighted by character count plus a punctuation bonus for natural pauses. Zero extra dependencies, instant, ~85% accurate. Default.
- **`aeneas`**: forced alignment via MFCC + dynamic time warping. Requires `aeneas` + system `espeak` + `ffmpeg`. ~99% accurate but adds 1-3 seconds of processing per sentence.

The aligners share a common interface, so swapping is `recite --align aeneas` away.

## Known limitations

- **macOS only.** `say`, `afplay`, and `afinfo` are Apple's. Replacing with `espeak-ng` + `paplay` would port the architecture to Linux but the binary wouldn't.
- **First sentence has a small delay.** The heuristic aligner is essentially free, but `say -o` itself takes 200–500 ms to synthesise.
- **Word alignment may drift on long sentences.** The heuristic accumulates small errors; aeneas is the fix for sentences longer than ~25 words.
- **Abbreviations may misalign.** `say` pronounces "Dr." as "Doctor" but the highlighter still maps to the written token "Dr."; minor visual hiccup.

## Project layout

```
recite/
├── recite/
│   ├── __main__.py    # CLI entry point
│   ├── app.py         # Textual App
│   ├── splitter.py    # sentence splitter
│   ├── synth.py       # say + background pre-render pool
│   ├── aligners.py    # heuristic + aeneas
│   ├── player.py      # afplay + SIGSTOP/SIGCONT
│   └── widgets.py     # SentenceWidget with per-word styling
├── claude-skill/
│   ├── recite/SKILL.md
│   └── INSTALL.md
├── pyproject.toml
├── Makefile
└── README.md
```

## Licence

MIT.
