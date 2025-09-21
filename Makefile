.PHONY: help install install-dev test test-all lint format type-check docs clean build publish

help:		## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:	## Install the package
	pip install -e .

install-dev:	## Install the package with development dependencies
	pip install -e .[dev,validation,examples]

test:		## Run tests with pytest
	pytest tests/ --cov=rest_framework --cov-report=term-missing

test-all:	## Run tests across all Python versions with tox
	tox

lint:		## Run linting checks
	black --check --diff rest_framework tests examples
	flake8 rest_framework tests examples
	isort --check-only --diff rest_framework tests examples

format:		## Format code with black and isort
	black rest_framework tests examples
	isort rest_framework tests examples

type-check:	## Run type checking with mypy
	mypy rest_framework

docs:		## Build documentation
	tox -e docs

clean:		## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .tox/
	rm -rf .pytest_cache/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:		## Build package
	python -m build

check-build:	## Check built package
	twine check dist/*

publish-test:	## Publish to Test PyPI
	twine upload --repository testpypi dist/*

publish:	## Publish to PyPI
	twine upload dist/*

examples:	## Run example scripts
	python examples/basic_example.py
	@echo "\n--- Running validation example (requires pydantic) ---"
	python examples/validation_example.py || echo "Skipped validation example (pydantic not available)"
	@echo "\n--- Running advanced example ---"
	python examples/advanced_example.py

dev-setup:	## Set up development environment
	pip install -e .[dev,validation,examples]
	pre-commit install || echo "pre-commit not available"

release-patch:	## Bump patch version and create release
	bump2version patch
	git push && git push --tags

release-minor:	## Bump minor version and create release
	bump2version minor
	git push && git push --tags

release-major:	## Bump major version and create release
	bump2version major
	git push && git push --tags

# Development workflow targets
dev:		## Run development workflow (format, lint, test)
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test

ci:		## Run CI workflow (lint, type-check, test-all)
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test-all

# Docker targets (optional)
docker-build:	## Build Docker image for testing
	docker build -t rest-framework:latest .

docker-test:	## Run tests in Docker
	docker run --rm rest-framework:latest pytest

# Package info
info:		## Show package information
	@echo "Package: rest-framework"
	@echo "Version: $$(python -c 'import rest_framework; print(rest_framework.__version__)')"
	@echo "Python: $$(python --version)"
	@echo "Platform: $$(python -c 'import platform; print(platform.platform())')"
