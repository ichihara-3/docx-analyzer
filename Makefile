.PHONY: install dev cli lint format clean

install:
	uv sync

dev:
	uv run uvicorn docx_analyzer.web:app --reload

cli:
	uv run docx-analyze --help

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
