# CryptoLens

Near real-time streaming pipeline that ingests aggregated trade events from Binance
WebSocket, publishes them to Apache Kafka, and writes Parquet files to MinIO (S3-compatible storage) via PySpark Structured Streaming.

```
Binance WebSocket (aggTrade)
         │
         ▼
  Python Producer
  (websocket-client)
         │  Avro + Schema Registry
         ▼
  Kafka topic: crypto.trades
         │
         ▼
  PySpark Structured Streaming
  (reads Avro, strips Confluent prefix)
         │  Parquet + Snappy, every 30s
         ▼
  MinIO (S3-compatible)
  trades/symbol=BTCUSDT/date=.../hour=.../
         │
         ▼
  (future) ClickHouse → Analytics
```

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker Desktop | latest | https://docs.docker.com/get-docker/ |
| Python | ≥ 3.11 | https://www.python.org/downloads/ |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

> **macOS / Linux only.** Windows users should use WSL2.

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd cryptolens_project

# 2. Copy environment template
cp .env.example .env

# 3. Start full infrastructure (Kafka + Schema Registry + Kafka UI + MinIO + Spark consumer)
make up

# 4. Wait ~60 s for all services to become healthy, then verify:
#    Kafka UI  → http://localhost:8080
#    MinIO     → http://localhost:9001  (user: minioadmin / pass: minioadmin)
#    Schema Registry → curl http://localhost:8081/subjects

# 5. Install Python dependencies
uv sync --extra dev

# 6. Start the Binance producer
make run
```

You should see JSON log lines like:

```json
{"log_level": "info", "timestamp": "2024-11-14T12:00:01Z", "event": "ws_connected", "url": "wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/ethusdt@aggTrade"}
{"log_level": "info", "timestamp": "2024-11-14T12:00:01Z", "event": "delivered", "topic": "crypto.trades", "offset": 0}
```

Stop with `Ctrl+C` — the producer flushes pending messages before exiting.

After ~30 seconds, Parquet files will appear in MinIO under `cryptolens/trades/`.

## Verification

| Check | Command |
|-------|---------|
| Kafka UI (topics, messages) | Open http://localhost:8080 in a browser |
| MinIO Console (Parquet files) | `make minio-ui` or open http://localhost:9001 |
| Registered Avro schemas | `curl http://localhost:8081/subjects` |
| Spark consumer logs | `make logs-spark` |

## Running Tests

```bash
# Producer tests (parsing + Avro serialization)
make test

# Spark consumer tests (requires pyspark installed)
uv sync --extra spark
make test-spark
```

Run the linter:

```bash
make lint
```

Auto-format the code:

```bash
make format
```

## Configuration

All settings are read from environment variables or a `.env` file in the project root.

### Producer

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `SCHEMA_REGISTRY_URL` | `http://localhost:8081` | Confluent Schema Registry URL |
| `BINANCE_WS_BASE_URL` | `wss://stream.binance.com:9443/stream` | Binance WebSocket base URL |
| `SYMBOLS` | `BTCUSDT,ETHUSDT` | Comma-separated trading pairs to stream |
| `KAFKA_TOPIC_TRADES` | `crypto.trades` | Target Kafka topic |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### MinIO / Spark consumer

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `http://localhost:9000` | MinIO S3 API endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | `cryptolens` | Bucket where Parquet files are written |
| `SPARK_TRIGGER_SECONDS` | `30` | How often Spark writes a micro-batch to MinIO |
| `SPARK_CHECKPOINT_DIR` | `s3a://cryptolens/checkpoints/trades` | Spark streaming checkpoint location |

## Project Structure

```
cryptolens_project/
├── docker/
│   ├── docker-compose.yml        # Kafka (KRaft) + Schema Registry + Kafka UI + MinIO + Spark
│   └── spark/
│       └── Dockerfile            # bitnami/spark:3.5.1 + Kafka/Avro/S3A JARs
├── src/
│   └── cryptolens/
│       ├── __main__.py            # Entry point: python -m cryptolens
│       ├── config.py              # Pydantic-settings configuration (producer + MinIO + Spark)
│       ├── logging.py             # structlog JSON setup
│       ├── schemas/
│       │   └── trade.avsc         # Avro schema for trade events
│       ├── binance/
│       │   ├── client.py          # WebSocket client + reconnect logic
│       │   └── parser.py          # Raw Binance JSON → Trade dict
│       ├── kafka/
│       │   └── producer.py        # SerializingProducer + AvroSerializer
│       └── spark/
│           └── consumer.py        # PySpark Structured Streaming → MinIO
├── tests/
│   ├── test_parsing.py            # Unit tests for message parsing
│   ├── test_serialization.py      # Avro schema round-trip tests
│   └── test_spark_consumer.py     # PySpark unit tests (local mode)
├── pyproject.toml                 # Dependencies (managed by uv)
├── uv.lock                        # Locked dependency versions
├── .env.example                   # Configuration template
├── Makefile                       # Development shortcuts
└── README.md
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make up` | Start all infrastructure (Kafka, MinIO, Spark consumer) |
| `make down` | Stop and remove all containers |
| `make run` | Start the Binance producer |
| `make run-spark` | Restart the Spark consumer container |
| `make logs` | Tail Kafka logs |
| `make logs-spark` | Tail Spark consumer logs |
| `make minio-ui` | Open MinIO Console in browser |
| `make test` | Run producer unit tests |
| `make test-spark` | Run Spark unit tests |
| `make lint` | Run ruff linter |
| `make format` | Auto-format code with ruff |

## Stopping the Infrastructure

```bash
make down
```

This stops and removes containers. Kafka data is persisted in `docker/kafka-data/` and
MinIO data in `docker/minio-data/` — both survive `make down`. To also remove data:

```bash
docker compose -f docker/docker-compose.yml down -v
rm -rf docker/kafka-data docker/minio-data
```
