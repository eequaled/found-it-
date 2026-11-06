PYTHON ?= python
.PHONY: install sqlc-generate generate validate check-generated test
install:
	$(PYTHON) -m pip install -e '.[test]'
sqlc-generate:
	$(PYTHON) -m scripts.prepare_plugin
	$(PYTHON) -m scripts.codegen generate
generate: sqlc-generate
validate:
	$(PYTHON) -m scripts.codegen validate
check-generated: sqlc-generate
	git diff --exit-code
test: validate check-generated
	ruff check .
	$(PYTHON) -m pytest -q
