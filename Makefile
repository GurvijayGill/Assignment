PYTHON ?= python

.PHONY: install test

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q -p no:cacheprovider
