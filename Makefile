.PHONY: install lint test audit check

install:  ## Install the package with dev dependencies
	pip install -e ".[dev]"

lint:  ## Static checks
	ruff check .

test:  ## Run the test suite
	pytest -q

audit:  ## Scan dependencies for known vulnerabilities
	pip-audit

check: lint test audit  ## Everything CI should run
