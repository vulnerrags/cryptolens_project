# CryptoLens

Near real-time streaming pipeline that ingests aggregated trade events from Binance
WebSocket and publishes them to Apache Kafka using Avro serialization.

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
  (future) PySpark Consumer → ClickHouse / Analytics
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

# 3. Start Kafka infrastructure (Kafka + Schema Registry + Kafka UI)
make up

# 4. Wait ~30 s for Kafka to become healthy, then verify:
#    Kafka UI  → http://localhost:8080
#    Schema Registry → curl http://localhost:8081/subjects

# 5. Install Python dependencies
uv sync --extra dev

# 6. Start the producer
make run
```

You should see JSON log lines like:

```json
{"log_level": "info", "timestamp": "2024-11-14T12:00:01Z", "event": "ws_connected", "url": "wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/ethusdt@aggTrade"}
{"log_level": "info", "timestamp": "2024-11-14T12:00:01Z", "event": "delivered", "topic": "crypto.trades", "offset": 0}
```

Stop with `Ctrl+C` — the producer flushes pending messages before exiting.

## Verification

| Check | Command |
|-------|---------|
| Kafka UI (topics, messages) | Open http://localhost:8080 in a browser |
| Registered Avro schemas | `curl http://localhost:8081/subjects` |
| Kafka topic message count | Kafka UI → Topics → `crypto.trades` |

## Running Tests

```bash
make test
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

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `SCHEMA_REGISTRY_URL` | `http://localhost:8081` | Confluent Schema Registry URL |
| `BINANCE_WS_BASE_URL` | `wss://stream.binance.com:9443/stream` | Binance WebSocket base URL |
| `SYMBOLS` | `BTCUSDT,ETHUSDT` | Comma-separated trading pairs to stream |
| `KAFKA_TOPIC_TRADES` | `crypto.trades` | Target Kafka topic |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Project Structure

```
cryptolens_project/
├── docker/
│   └── docker-compose.yml        # Kafka (KRaft) + Schema Registry + Kafka UI
├── src/
│   └── cryptolens/
│       ├── __main__.py            # Entry point: python -m cryptolens
│       ├── config.py              # Pydantic-settings configuration
│       ├── logging.py             # structlog JSON setup
│       ├── schemas/
│       │   └── trade.avsc         # Avro schema for trade events
│       ├── binance/
│       │   ├── client.py          # WebSocket client + reconnect logic
│       │   └── parser.py          # Raw Binance JSON → Trade dict
│       └── kafka/
│           └── producer.py        # SerializingProducer + AvroSerializer
├── tests/
│   ├── test_parsing.py            # Unit tests for message parsing
│   └── test_serialization.py     # Avro schema round-trip tests
├── pyproject.toml                 # Dependencies (managed by uv)
├── uv.lock                        # Locked dependency versions
├── .env.example                   # Configuration template
├── Makefile                       # Development shortcuts
└── README.md
```

## Stopping the Infrastructure

```bash
make down
```

This stops and removes containers.  Kafka data is persisted in a Docker volume
(`kafka-data`) and survives `make down`.  To also remove the volume:

```bash
docker compose -f docker/docker-compose.yml down -v
```
