# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make up                # Start infrastructure (Kafka, Schema Registry, MinIO, Spark, ClickHouse)
make down              # Stop containers
make run               # Start Binance WebSocket producer (uv run python -m cryptolens)
make test              # Run producer tests (pytest)
make test-spark        # Run Spark consumer tests (requires: uv sync --extra spark)
make lint              # Ruff linter
make format            # Ruff formatter
make ch-client         # ClickHouse CLI (default/default)
uv sync --extra dev    # Install dev dependencies
```

Run a single test: `uv run pytest tests/test_parsing.py -v -k test_name`

## Architecture

**Pipeline:** Binance aggTrade WebSocket -> Kafka (Avro + Schema Registry) -> PySpark Structured Streaming -> MinIO (Parquet) -> ClickHouse (S3Queue + MergeTree)

- **Producer** (`src/cryptolens/`): Sync `websocket-client` connects to Binance combined stream, parses aggTrade JSON, serializes with `confluent_kafka.SerializingProducer` + `AvroSerializer`, publishes to `crypto.trades` topic. Entry point: `__main__.py`.
- **Spark consumer** (`src/cryptolens/spark/consumer.py`): PySpark Structured Streaming reads Avro from Kafka, strips Confluent 5-byte prefix, writes Hive-partitioned Parquet (`symbol=/date=/hour=`) to MinIO every 30s.
- **ClickHouse sink** (`docker/clickhouse/initdb.d/01_schema.sql`): S3Queue polls MinIO Parquet files, Materialized View converts Unix-ms to DateTime64 and extracts Hive partition columns from `_path`, inserts into MergeTree table.

Configuration: Pydantic-settings in `src/cryptolens/config.py`, reads from env vars / `.env` file.

## Key Conventions

- **Kafka serialization**: Use `SerializingProducer` + `AvroSerializer` (never deprecated `AvroProducer`)
- **WebSocket**: `websocket-client` (sync, callback-based) — not asyncio
- **Binance stream**: `aggTrade` (aggregated trades), not `trade`
- **Logging**: structlog + orjson, JSON to stdout
- **Style**: PEP 8, 88-char line length, ruff enforced (`E`, `F`, `I` rules). Type hints on all public signatures.
- **Package manager**: uv (not pip)
- **Docker**: KRaft mode Kafka (no ZooKeeper), compose file at `docker/docker-compose.yml`

## ClickHouse Gotchas

- `listen_host=0.0.0.0` required via `docker/clickhouse/config.d/network.xml` (default image listens on loopback only)
- Built-in Keeper (`config.d/keeper.xml`) required for S3Queue in any mode
- In the MV, ClickHouse resolves aliases left-to-right: `date`/`hour` columns see `trade_time` as the already-aliased DateTime64, so use `toDate(trade_time, 'UTC')` directly
- ClickHouse native port mapping: 9004 (host) -> 9000 (container)
