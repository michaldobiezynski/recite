# Installing the recite skill into Claude Code

The skill in this directory teaches Claude Code when and how to invoke `recite`.

## Project-level install (recommended for trying it out)

Drop the skill into the repo you're working in:

```bash
mkdir -p .claude/skills
cp -r claude-skill/recite .claude/skills/
```

Any `claude` session started in that directory will see and load the skill.

## User-level install (available in every project)

```bash
mkdir -p ~/.claude/skills
cp -r claude-skill/recite ~/.claude/skills/
```

## Verify

In a fresh Claude Code session, ask:

> read this file aloud: README.md

Claude should resolve to `recite README.md` and launch it. If the skill isn't being picked up, check that `~/.claude/skills/recite/SKILL.md` exists and that the frontmatter is intact (no missing `---` delimiters).

## Updating

The skill is a single markdown file. Edit `SKILL.md` and re-copy. Claude Code reads it fresh on each session start.
