# FastAPI agent service — common tasks.
# ▢ TODO: rename IMAGE to your service.
IMAGE ?= fastapi-agent-service
PORT  ?= 8000

.PHONY: help install run test check lint typecheck docker-build docker-run

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install the project with dev extras.
	pip install -e ".[dev]"

run:  ## Run the API locally with autoreload (http://localhost:$(PORT)).
	uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

test:  ## Run the test suite (MOCK mode; no API key needed).
	pytest

lint:  ## Lint with ruff.
	ruff check app

typecheck:  ## Type-check with mypy.
	mypy app

check: lint typecheck test  ## Lint + type-check + test (the pre-commit gate).

docker-build:  ## Build the container image.
	docker build -t $(IMAGE) .

docker-run:  ## Run the container, passing your local .env.
	docker run --rm -p $(PORT):8000 --env-file .env $(IMAGE)
