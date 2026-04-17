format: lint
	uv run -- ruff format

lint:
	uv run -- ruff check --fix
	uv run -- ty check

test:
	uv run -- pytest -v -n auto

install:
	uv sync --all-extras
	uv run -- prek install

upgrade:
	uv sync --upgrade --all-extras