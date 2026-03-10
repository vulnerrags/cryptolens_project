.PHONY: up down run lint format test logs run-spark logs-spark test-spark minio-ui ch-client logs-ch

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

run-spark:
	$(COMPOSE) up -d spark-consumer

logs-spark:
	$(COMPOSE) logs -f spark-consumer

test-spark:
	uv run pytest tests/test_spark_consumer.py -v

minio-ui:
	@echo "MinIO Console: http://localhost:9001  (user: minioadmin / pass: minioadmin)"
	open http://localhost:9001

ch-client:
	docker exec -it cryptolens-clickhouse clickhouse-client --user default --password default --database cryptolens

logs-ch:
	$(COMPOSE) logs -f clickhouse
