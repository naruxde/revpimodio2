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
	# Start with empty environment
	"$(SYSTEM_PYTHON)" -m venv "$(VENV_PATH)"
	source "$(VENV_PATH)/bin/activate" && \
		python3 -m pip install --upgrade pip && \
		python3 -m pip install -r requirements.txt
	exit 0

venv-ssp:
	# Include system installed site-packages and add just missing modules
	"$(SYSTEM_PYTHON)" -m venv --system-site-packages "$(VENV_PATH)"
	source "$(VENV_PATH)/bin/activate" && \
		python3 -m pip install --upgrade pip && \
		python3 -m pip install -r requirements.txt
	exit 0

.PHONY: venv-info venv venv-ssp

## Build steps
test:
	PYTHONPATH=src "$(PYTHON)" -m pytest tests

build:
	"$(PYTHON)" -m setup sdist
	"$(PYTHON)" -m setup bdist_wheel

install: build
	"$(PYTHON)" -m pip install dist/$(PACKAGE)-$(APP_VERSION)-*.whl

uninstall:
	"$(PYTHON)" -m pip uninstall --yes $(PACKAGE)

.PHONY: test build install uninstall

## Documentation
docs:
	"$(PYTHON)" -m sphinx.cmd.build -b html docs docs/_build/html

.PHONY: docs

## Clean
clean:
	# PyTest caches
	rm -rf .pytest_cache
	# Build artifacts
	rm -rf build dist src/*.egg-info
	# PyInstaller created files
	rm -rf *.spec

distclean: clean
	# Virtual environment
	rm -rf "$(VENV_PATH)"

.PHONY: clean distclean
