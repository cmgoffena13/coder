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

compile:
	uv run -- nuitka src/app.py \
		--lto=yes \
		--output-filename=coder \
		--python-flag=no_warnings \
		--include-package=src \
		--include-data-dir=src/internal=src/internal \
		--include-data-files=pyproject.toml=pyproject.toml \
		--noinclude-data-files=src/tests/* \
		--output-dir=dist/

compile-zip: compile
	cd dist && rm -f coder-dist.zip && zip -r coder-dist.zip coder.dist