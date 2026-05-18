---
name: recite
description: Use this skill when the user wants to LISTEN to text — reading something aloud, narrating a file, hearing a draft spoken back, listening to a long document. Trigger phrases include "read this aloud", "recite this", "narrate this", "speak this", "TTS this", "read this back to me", "listen to this", "hear this out loud", and any request involving the `recite` CLI tool. Also use when the user asks to listen to error logs, drafts, articles, emails, or any text content in the current conversation or working directory. Do NOT use for: text-to-speech audio file generation (use `say -o file.aiff` directly), real-time dictation/speech-to-text, or content the user only wants summarised.
---

# recite — TTS player for the terminal

`recite` is a Textual TUI text-to-speech player for macOS. It wraps `say` and `afplay`, splits input into sentences, pre-renders each, runs word-timing alignment, and plays back with karaoke-style word-level highlighting plus pause/seek/replay controls.

## How to invoke it

`recite` lives on the user's PATH (typically `~/.local/bin/recite`, installed via pipx). It accepts input three ways:

1. **A file path as argument** — preferred when the content is already in a file on disk:
   ```bash
   recite path/to/draft.md
   ```

2. **Piped stdin** — preferred when the content is generated on the fly:
   ```bash
   cat README.md | recite
   tail -n 30 app.log | recite
   ```

3. **Clipboard** — invoked with no arguments, reads from `pbpaste`:
   ```bash
   recite
   ```

## Decision rules

Pick the invocation with least friction:

- **Content already in a file in the working directory** → `recite <path>`
- **Content is a snippet you've just produced (a draft, a summary, an error)** → write it to a tempfile with a heredoc, then `recite <tempfile>`. Don't pipe long strings through `echo` — quoting breaks.
- **Content is on the user's clipboard** → tell them to run `recite` themselves; don't try to read their clipboard for them.
- **Content is code or a list** → `recite` reads line-by-line for non-prose. Warn the user that code will sound rough; sometimes a summary is more useful.

## Patterns

**Read a file**:
```bash
recite ~/Documents/draft.md
```

**Read something you just drafted**:
```bash
cat > /tmp/recite-input.txt <<'EOF'
$DRAFT_TEXT_GOES_HERE
EOF
recite /tmp/recite-input.txt
```
(Use a heredoc to avoid shell-quoting nightmares.)

**Read the latest log entry**:
```bash
tail -n 30 app.log | recite
```

**Read with a different voice or rate**:
```bash
recite --voice Karen draft.md          # Karen is Australian
recite --voice Daniel --rate 220 draft.md
```

**Karaoke-accurate alignment** (only if user has installed `recite[align]`):
```bash
recite --align aeneas draft.md
```

Common English voices on a modern Mac: Daniel (UK), Karen (AU), Moira (IE), Samantha (US), Tessa (ZA), Alex (US), Fiona (Scottish). Run `say -v ?` to list installed voices.

## Inside the app — keys to mention to the user

When you launch `recite` for them, briefly remind them of the controls if they may not know:

- `space` — pause / resume
- `j` / `k` — next / previous sentence
- `r` — replay current sentence
- `+` / `-` — faster / slower
- `v` — cycle voice
- `q` — quit

## Don't do these

- **Don't paste raw text into a `recite "$TEXT"` invocation.** It doesn't take text as an argument. Quoting breaks for anything multi-line. Always use stdin or a file.
- **Don't launch `recite` in the background.** It's a foreground TUI — backgrounding will not work, and the user wants to see and control it.
- **Don't run `recite` inside a script that captures stdout.** The TUI writes to a terminal, not a pipe — capturing output produces garbled escape sequences.
- **Don't synthesise long text yourself with `say -o` when `recite` is available.** The whole point of this tool is the player UI.

## Verifying installation

```bash
command -v recite >/dev/null || echo "recite not installed; see project README"
```

If it's not installed, point the user at the project — don't try to install it on their behalf without asking.
