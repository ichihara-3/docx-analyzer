.PHONY: install dev cli lint format clean

install:
	uv sync

dev:
	uv run docx-web

cli:
	uv run docx-analyze --help

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
