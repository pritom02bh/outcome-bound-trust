# Reproduce: every table and figure is rebuilt from runs/ only (F12). Nothing here calls a paid API.
PY ?= .venv/bin/python

.PHONY: test results lock

test:
	PYTHONPATH=. $(PY) -m pytest -q

results:
	PYTHONPATH=. $(PY) -m eval.results --runs runs --out results

lock:
	.venv/bin/pip freeze --exclude-editable > requirements.lock
