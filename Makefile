# readmefetch: every repo answers the same verbs (see ../Makefile.standard).
# Run `make` for the list. Nothing here needs installing first: commands run the
# package straight from src/ with the Python on your PATH (or .venv after `make setup`).

# ─── Identity (the only part that differs between repos) ─────────────────────
# No apostrophes in any of these four: they are interpolated into a
# single-quoted shell string in the help recipe.
PROJECT       := readmefetch
TAGLINE       := an animated neofetch-style terminal for GitHub profile READMEs
# `=` and not `:=`: with `:=` these expand before the variables they cite are
# defined further down, and the help footer prints empty values with no error.
HELP_VARS      = CONFIG=$(CONFIG) PORT=$(PORT)
HELP_EXAMPLE   = make web CONFIG=../my-profile/readmefetch.toml

# ─── Preamble ────────────────────────────────────────────────────────────────
# -e stops a recipe at the first failing command; -o pipefail stops a gate that
# pipes through a filter from reporting the filter's exit code instead of the
# command's — without it, a suite that fails into `tail` "passes".
SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -eo pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS     += --no-print-directory

# ─── Colour ──────────────────────────────────────────────────────────────────
# MAKE_TERMOUT (GNU Make >= 4.1) is set only when stdout is a terminal, and is
# the only reliable test available here: `test -t 1` inside $(shell ...) always
# reports false, because make captures that command's stdout through a pipe.
# So `make help | less` and CI logs stay clean. NO_COLOR disables, FORCE_COLOR
# overrides both.
COLOR ?= $(if $(MAKE_TERMOUT),1,0)
ifdef NO_COLOR
  COLOR := 0
endif
ifdef FORCE_COLOR
  COLOR := 1
endif
ifeq ($(COLOR),1)
  # Real ESC bytes, so a plain `echo` renders them without needing -e.
  C_HEAD := $(shell printf '\033[1m')
  C_CMD  := $(shell printf '\033[36m')
  C_OK   := $(shell printf '\033[32m')
  C_WARN := $(shell printf '\033[33m')
  C_ERR  := $(shell printf '\033[31m')
  C_DIM  := $(shell printf '\033[2m')
  C_OFF  := $(shell printf '\033[0m')
endif

# Explains why a core verb does not apply here, then fails.
NA = @printf '  $(C_ERR)make $@$(C_OFF) does not apply to $(PROJECT).\n  $(C_DIM)%s$(C_OFF)\n\n' $(1) >&2; exit 2

# Width of the target-name column in help; widen it where names are long.
HELP_PAD ?= 18

# PROJECT, TAGLINE, HELP_VARS and HELP_EXAMPLE are interpolated into a
# single-quoted shell string below, so none of them may contain an apostrophe.
##@ General
.PHONY: help
help: ## List the available targets
	@printf '\n  $(C_HEAD)$(PROJECT)$(C_OFF) — $(TAGLINE)\n'
	@printf '  $(C_DIM)usage: make <target>$(C_OFF)\n'
	@awk 'BEGIN { FS = ":.*?## " } \
	  /^##@ / { printf "\n  $(C_HEAD)%s$(C_OFF)\n", substr($$0, 5); next } \
	  /^[a-zA-Z0-9_.-]+:.*?## / { printf "    $(C_CMD)%-$(HELP_PAD)s$(C_OFF) %s\n", $$1, $$2 }' \
	  $(MAKEFILE_LIST)
	@printf '\n  $(C_DIM)Variables:$(C_OFF) $(HELP_VARS)\n'
	@printf '  $(C_DIM)Example:$(C_OFF)   $(HELP_EXAMPLE)\n\n'

# ─── End of the shared block ─────────────────────────────────────────────────

# Your own config (gitignored here). `make web` starts from an example when it is missing.
CONFIG ?= readmefetch.toml
PORT   ?= 8765
VENV   := .venv
PY     := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
RUFF   := $(if $(wildcard $(VENV)/bin/ruff),$(VENV)/bin/ruff,ruff)
RF     := PYTHONPATH=src $(PY) -m readmefetch
DEMO   := examples/readmefetch.toml

##@ Setup
.PHONY: setup
setup: ## First run on a fresh clone: .venv with readmefetch, Pillow (GIFs) and ruff
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -e ".[dev]"
	@printf '\n  $(C_OK)Ready.$(C_OFF) Next: $(C_CMD)make dev$(C_OFF)\n\n'

##@ Development
.PHONY: dev
dev: web ## The fast iteration loop: the web editor with a live preview

.PHONY: build
build: ## Build the wheel into dist/
	$(PY) -m pip wheel --quiet --no-deps --wheel-dir dist .
	@ls dist/*.whl

.PHONY: run
run: ## Show CONFIG in this terminal
	$(RF) print -c $(CONFIG)

##@ Gates
.PHONY: test
test: ## Run the test suite once (the GIF test needs Pillow and Chrome, Chromium, Brave or Edge)
	PYTHONPATH=src $(PY) -m unittest discover -s tests

.PHONY: lint
lint: ## Lint with ruff
	@command -v $(RUFF) >/dev/null || { printf '  $(C_ERR)ruff not found.$(C_OFF) Run $(C_CMD)make setup$(C_OFF) or pipx install ruff\n' >&2; exit 1; }
	$(RUFF) check src tests tools
	node --check src/readmefetch/web/app.js 2>/dev/null || ! command -v node >/dev/null

.PHONY: check
check: lint test ## Fast gate: lint, then tests

.PHONY: verify
verify: check build ## Full gate: check, then a production build

.PHONY: fmt
fmt: ## Format the tree in place
	$(call NA,'No formatter is configured: the code is hand-aligned and ruff format would reflow it. Use make lint (ruff check --fix fixes what it can).')

##@ readmefetch
.PHONY: web
web: ## The web editor for CONFIG on 127.0.0.1:PORT, opened in your browser
	$(RF) web -c $(CONFIG) --port $(PORT) --open

.PHONY: render
render: ## Write the SVG (and any badges) for CONFIG
	$(RF) render -c $(CONFIG)

.PHONY: gif
gif: ## Export CONFIG as a GIF (needs Pillow and a Chromium-family browser)
	$(RF) gif -c $(CONFIG)

.PHONY: badges
badges: ## Write only the badges of CONFIG and print the README snippet
	$(RF) badges -c $(CONFIG)

.PHONY: demo
demo: ## Regenerate examples/demo.svg, demo.gif and the example badges (offline numbers)
	$(RF) render -c $(DEMO) --offline
	$(RF) gif -c $(DEMO) --offline --fps 8

.PHONY: logos
logos: ## List the built-in logos and where their art comes from
	$(RF) logos

.PHONY: vendor
vendor: ## Re-download third-party art and icons from their pinned releases (needs the network)
	$(PY) tools/vendor_art.py
	$(PY) tools/vendor_icons.py

##@ Cleaning
.PHONY: clean
clean: ## Remove build output and caches, never configs or rendered images
	rm -rf build dist src/*.egg-info .ruff_cache
	find . -name __pycache__ -type d -prune -not -path './$(VENV)/*' -exec rm -rf {} +

.PHONY: distclean
distclean: clean ## clean, plus the .venv
	rm -rf $(VENV)
