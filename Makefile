SHELL        := bash
MAKEFLAGS     = --no-print-directory --no-builtin-rules
.DEFAULT_GOAL = all

# Variables
PACKAGE = revpimodio2

# If virtualenv exists, use it. If not, use PATH to find, except python3
SYSTEM_PYTHON  = /usr/bin/python3
PYTHON         = $(or $(wildcard venv/bin/python), $(SYSTEM_PYTHON))

all: build

.PHONY: all

## Environment
venv:
	$(SYSTEM_PYTHON) -m venv venv
	source venv/bin/activate && \
		python3 -m pip install --upgrade pip && \
		python3 -m pip install -r requirements.txt
	exit 0

.PHONY: venv

## Build, install
build:
	$(PYTHON) -m setup sdist
	$(PYTHON) -m setup bdist_wheel

install: build
	$(PYTHON) -m pip install dist/$(PACKAGE)-*.whl

.PHONY: build install

## Clean
clean:
	rm -rf build dist src/*.egg-info *.spec

clean-all: clean
	rm -R venv

.PHONY: clean clean-all
