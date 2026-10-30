PYTHON ?= python
SQLC ?= sqlc
.PHONY: install generate validate check-generated test
install:
	$(PYTHON) -m pip install -e '.[test]'
generate:
	$(PYTHON) -m scripts.prepare_plugin
	$(SQLC) generate
validate:
	$(PYTHON) -m scripts.codegen validate
check-generated:
	$(PYTHON) -m scripts.prepare_plugin
	$(PYTHON) -m scripts.codegen check
test: validate check-generated
	ruff check .
	$(PYTHON) -m pytest -q
