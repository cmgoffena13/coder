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

update:
	uv sync --upgrade --all-extras

publish:
	@test -n "$(version)" || (echo >&2 "usage: make publish version=v1.2.3"; exit 1)
	git tag -a "$(version)" -m "Release $(version)"
	git push origin "$(version)"

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