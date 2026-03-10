.PHONY: up down run lint format test logs

COMPOSE := docker compose -f docker/docker-compose.yml

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

run:
	uv run python -m cryptolens

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

test:
	uv run pytest tests/ -v

logs:
	$(COMPOSE) logs -f kafka
