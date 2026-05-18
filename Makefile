.PHONY: help install install-align link uninstall reinstall run dev test lint clean

help:
	@echo 'Targets:'
	@echo '  link           pipx install -e .  (edits to source take effect on next `recite` launch)'
	@echo '  install        pipx install . (uninstall-first; heuristic aligner only)'
	@echo '  install-align  pipx install ".[align]" (adds aeneas; needs brew install espeak ffmpeg)'
	@echo '  reinstall      alias for install'
	@echo '  uninstall      pipx uninstall recite'
	@echo '  dev            pip install -e . in current env'
	@echo '  run            python -m recite (reads clipboard)'
	@echo '  test           pytest'
	@echo '  lint           ruff check'
	@echo '  clean          remove build artefacts'

# Editable install: pipx links the package back to this source tree. Edits to
# recite/*.py take effect the next time `recite` is launched; no reinstall
# step needed. Uninstall first because pipx 1.12 + uv silently no-ops --force
# when a venv already exists.
link:
	-pipx uninstall recite
	pipx install --editable .

# `pipx install --force .` is unreliable on pipx 1.12 + uv backend: the uv
# venv refuses to overwrite itself and pipx falls through to a no-op,
# leaving stale source in place. Uninstall first to guarantee a fresh build.
install:
	-pipx uninstall recite
	pipx install .

install-align:
	@command -v espeak >/dev/null || { echo 'install espeak first: brew install espeak ffmpeg'; exit 1; }
	-pipx uninstall recite
	pipx install '.[align]'

reinstall: install

uninstall:
	pipx uninstall recite

dev:
	pip install -e '.[dev]'

run:
	python -m recite

test:
	pytest

lint:
	ruff check recite/ tests/

clean:
	rm -rf build/ dist/ *.egg-info/ .ruff_cache/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
