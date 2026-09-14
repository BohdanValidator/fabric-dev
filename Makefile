FAB     := C:\tools\fabcli\Scripts\fab.exe
PY      := py -3.11
VENV    := .venv
PYTHON  := $(VENV)/Scripts/python.exe

empty   :=
space   := $(empty) $(empty)

-include .env

WS      ?= $(FABRIC_WORKSPACE)
WSDIR   := $(subst $(space),_,$(WS))
DIR     := ./notebooks/$(WSDIR)
NB      ?=

.PHONY: help use envs login list list-nb pull pull-all push run setup reinstall check freeze

help:
	@echo "Workspace: $(WS)  ->  $(DIR)"
	@echo "Override with WS=\"Other Workspace\""
	@echo ""
	@echo "  make envs                 - list available env files"
	@echo "  make use ENV=semantic     - activate envs/semantic.env"
	@echo ""
	@echo "  make list-nb              - list notebooks in the workspace"
	@echo "  make pull NB=name         - download one notebook"
	@echo "  make pull-all             - download every item in the workspace"
	@echo "  make push NB=name         - upload one notebook"
	@echo "  make run NB=name          - run notebook on Fabric Spark"
	@echo ""
	@echo "  make setup                - create .venv and install deps"
	@echo "  make reinstall            - reinstall deps into existing .venv"
	@echo "  make check                - show python version, check deps"
	@echo "  make freeze               - write requirements-lock.txt"

envs:
	@dir /b envs\*.env

use:
	@if "$(ENV)"=="" (echo ENV required: make use ENV=semantic && exit 1)
	@if not exist "envs\$(ENV).env" (echo No such env: envs\$(ENV).env && exit 1)
	@copy /y "envs\$(ENV).env" ".env" >nul
	@echo Active env is now $(ENV)

login:
	$(FAB) auth login

list:
	$(FAB) ls -l "$(WS).Workspace"

list-nb:
	$(FAB) ls -l "$(WS).Workspace" | findstr /i notebook

pull:
	@if "$(NB)"=="" (echo NB required: make pull NB=name && exit 1)
	@if not exist "$(subst /,\,$(DIR))" mkdir "$(subst /,\,$(DIR))"
	$(FAB) export "$(WS).Workspace/$(NB).Notebook" -o "$(DIR)" --format .ipynb -f

pull-all:
	$(PYTHON) pull_notebooks.py "$(WS)" "$(DIR)"
push:
	@if "$(NB)"=="" (echo NB required: make push NB=name && exit 1)
	$(PYTHON) fix_metadata.py "$(DIR)/$(NB).Notebook/notebook-content.ipynb"
	$(FAB) import "$(WS).Workspace/$(NB).Notebook" -i "$(DIR)/$(NB).Notebook" --format .ipynb -f

run:
	@if "$(NB)"=="" (echo NB required: make run NB=name && exit 1)
	$(FAB) job run "$(WS).Workspace/$(NB).Notebook"

setup:
	@if exist $(VENV) (echo Remove .venv first, or run make reinstall && exit 1)
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-local.txt

reinstall:
	$(PYTHON) -m pip install --force-reinstall -r requirements-local.txt

check:
	$(PYTHON) -c "import sys; print(sys.version)"
	$(PYTHON) -m pip check

freeze:
	$(PYTHON) -m pip freeze > requirements-lock.txt