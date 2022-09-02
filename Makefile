LINT_TARGETS := $(wildcard *.py) algorw/

all: lint

lint: flake8 typecheck

flake8:
	flake8 $(LINT_TARGETS)

typecheck:
	mypy $(LINT_TARGETS)

.PHONY: all lint flake8 typecheck

# Para producción.
deploy: venv
	venv/bin/pip-sync requirements.txt

# Para desarrollo.
sync: requirements.txt requirements.dev.txt
	@echo pip-sync $^
	@venv/bin/pip-sync $^

%.txt: %.in venv
	@echo pip-compile $<
	@env CUSTOM_COMPILE_COMMAND="make $@" venv/bin/pip-compile $<

venv:
	[ -d venv ] || {            \
	    virtualenv -p 3.8 venv; \
	    venv/bin/pip install --upgrade pip;       \
	    venv/bin/python -m pip install pip-tools; \
	}

.PHONY: deploy sync
