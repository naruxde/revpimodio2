SHELL        := bash
MAKEFLAGS     = --no-print-directory --no-builtin-rules
.DEFAULT_GOAL = all

# Variables
PACKAGE = revpimodio2

# Set path to create the virtual environment with package name
ifdef PYTHON3_VENV
VENV_PATH = $(PYTHON3_VENV)/$(PACKAGE)
else
VENV_PATH = venv
endif

# If virtualenv exists, use it. If not, use PATH to find commands
SYSTEM_PYTHON  = python3
PYTHON         = $(or $(wildcard $(VENV_PATH)/bin/python), $(SYSTEM_PYTHON))

all: build docs

.PHONY: all

## Environment
venv-info:
	echo Using path: "$(VENV_PATH)"
	exit 0

venv:
	$(SYSTEM_PYTHON) -m venv "$(VENV_PATH)"
	source $(VENV_PATH)/bin/activate && \
		python3 -m pip install --upgrade pip && \
		python3 -m pip install -r requirements.txt
	exit 0

.PHONY: venv-info venv

## Build, install
build:
	$(PYTHON) -m setup sdist
	$(PYTHON) -m setup bdist_wheel

install: build
	$(PYTHON) -m pip install dist/$(PACKAGE)-*.whl

docs:
	$(PYTHON) -m sphinx.cmd.build -b html docs docs/_build/html

.PHONY: build docs install

## Clean
clean:
	rm -rf build docs/_build dist src/*.egg-info *.spec

clean-all: clean
	rm -R $(VENV_PATH)

.PHONY: clean clean-all
