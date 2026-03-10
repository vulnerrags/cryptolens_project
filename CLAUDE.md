# CryptoLens — Claude Instructions

> **Self-update rule:** After any significant change (new feature, new dependency, new file, renamed file, changed architecture decision), review and update this file accordingly before finishing the task.

---

## Project Overview

Near real-time Binance aggTrade → Kafka → MinIO → ClickHouse streaming pipeline.

```
Binance WebSocket
  (aggTrade stream)
        │
        ▼
  BinanceWSClient          src/cryptolens/binance/client.py
  parse_trade()            src/cryptolens/binance/parser.py
        │  Avro + Schema Registry
        ▼
  Kafka topic: crypto.trades
        │
        ▼
  PySpark Structured Streaming  src/cryptolens/spark/consumer.py
        │  Parquet + Snappy
        ▼
  MinIO (s3a://cryptolens/trades/)
  partitioned by symbol/date/hour
        │
        ▼
  ClickHouse S3Queue → MergeTree
  (docker/clickhouse/initdb.d/01_schema.sql)
```

Source: Binance WebSocket combined stream — **no API key required**.
Language: Python 3.11+, managed with `uv` + `pyproject.toml`.

---

## Technology Stack

| Component | Library / Version | Notes |
|---|---|---|
| WebSocket | `websocket-client >=1.7` | Sync, callback-based — **not asyncio** |
| Kafka producer | `confluent-kafka[avro] >=2.4` | `SerializingProducer` + `AvroSerializer` |
| Schema serialization | Avro + Confluent Schema Registry | TopicNameStrategy |
| Settings | `pydantic-settings >=2.0` | Reads `.env` file |
| Logging | `structlog >=24` + `orjson >=3.9` | JSON to stdout |
| Spark consumer | `pyspark >=3.5` (optional dep) | Structured Streaming |
| Infrastructure | Docker Compose, KRaft (cp-kafka 7.6.1) | No ZooKeeper |
| Object storage | MinIO | S3-compatible, path-style access |
| ClickHouse | `clickhouse/clickhouse-server:25.3` | S3Queue → MergeTree sink |
| Test runner | `pytest >=8` | |
| Linter/formatter | `ruff >=0.4` | max line length 88 |

---

## File Structure

```
cryptolens_project/
├── CLAUDE.md                          ← this file
├── Makefile                           ← all dev commands
├── pyproject.toml                     ← uv-managed deps
├── .env / .env.example                ← env config
├── docker/
│   ├── docker-compose.yml             ← Kafka KRaft + Schema Registry + Kafka UI + MinIO + Spark + ClickHouse
│   ├── spark/
│   │   └── Dockerfile                 ← PySpark image with required JARs
│   └── clickhouse/
│       ├── config.d/
│       │   ├── keeper.xml             ← ClickHouse Keeper (built-in ZooKeeper replacement)
│       │   └── network.xml            ← listen_host=0.0.0.0 (required for host access)
│       └── initdb.d/
│           └── 01_schema.sql          ← S3Queue + MergeTree + Materialized View
└── src/cryptolens/
    ├── __main__.py                    ← entry point (python -m cryptolens)
    ├── config.py                      ← Settings (pydantic-settings)
    ├── logging.py                     ← structlog JSON setup
    ├── schemas/
    │   └── trade.avsc                 ← Avro schema for Trade record
    ├── binance/
    │   ├── client.py                  ← BinanceWSClient + reconnect loop
    │   └── parser.py                  ← parse_trade() mapper
    ├── kafka/
    │   └── producer.py                ← TradeProducer wrapper
    └── spark/
        └── consumer.py                ← PySpark Structured Streaming job
tests/
├── conftest.py
├── test_parsing.py                    ← parse_trade() unit tests
├── test_serialization.py              ← Avro schema round-trip tests (fastavro)
└── test_spark_consumer.py             ← Spark consumer unit tests (local mode)
```

---

## Architecture Decisions (Critical)

### DO NOT
- Use `AvroProducer` — it is **deprecated**. Always use `SerializingProducer` + `AvroSerializer`.
- Use `asyncio` for the WebSocket layer — `websocket-client` is sync/callback-based by design.
- Use ZooKeeper — infrastructure runs **KRaft mode** only.
- Add ZooKeeper to docker-compose.yml.
- Use virtual-hosted style S3 URLs with MinIO — **path-style access** (`fs.s3a.path.style.access=true`) is required.
- Pass raw Avro bytes directly to `from_avro()` from a Confluent Kafka topic — must **strip the 5-byte Confluent wire-format prefix** first (`substring(value, 6, length(value) - 5)`).

### Key Design Choices
- **Stream type**: `aggTrade` (not `trade`) — aggregated per ms, lower volume.
- **Topic**: `crypto.trades`, symbol as message key.
- **Binance WS URL**: `wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/...`
- **Reconnect**: exponential backoff 1s→60s + jitter; reset backoff if connection lived ≥5s.
- **Ping/pong**: handled by `websocket-client` (`ping_interval=20, ping_timeout=10`).
- **Binance 24h disconnect**: handled transparently by the reconnect loop.
- **Spark partitioning**: `symbol / date / hour` derived from `trade_time` (ms epoch UTC).
- **Spark shuffle partitions**: set to 4 (single-node, avoids 200 tiny files).

---

## Avro Schema — Trade Record

Fields in `src/cryptolens/schemas/trade.avsc`:

| Field | Type | Source (`data.*`) |
|---|---|---|
| `symbol` | string | `s` |
| `agg_trade_id` | long | `a` |
| `price` | string | `p` (decimal string, preserve precision) |
| `quantity` | string | `q` (decimal string) |
| `first_trade_id` | long | `f` |
| `last_trade_id` | long | `l` |
| `trade_time` | long | `T` (ms epoch) |
| `is_buyer_maker` | boolean | `m` |
| `ingestion_time` | long | `int(time.time() * 1000)` at producer |

---

## Settings (`config.py` — `Settings`)

| Env var | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | |
| `SCHEMA_REGISTRY_URL` | `http://localhost:8081` | |
| `BINANCE_WS_BASE_URL` | `wss://stream.binance.com:9443/stream` | |
| `SYMBOLS` | `["BTCUSDT","ETHUSDT"]` | |
| `KAFKA_TOPIC_TRADES` | `crypto.trades` | |
| `LOG_LEVEL` | `INFO` | |
| `MINIO_ENDPOINT` | `http://localhost:9000` | |
| `MINIO_ACCESS_KEY` | `minioadmin` | |
| `MINIO_SECRET_KEY` | `minioadmin` | |
| `MINIO_BUCKET` | `cryptolens` | |
| `SPARK_TRIGGER_SECONDS` | `30` | |
| `SPARK_CHECKPOINT_DIR` | `s3a://cryptolens/checkpoints/trades` | |
| `CLICKHOUSE_HOST` | `localhost` | |
| `CLICKHOUSE_HTTP_PORT` | `8123` | HTTP interface |
| `CLICKHOUSE_NATIVE_PORT` | `9004` | Native TCP (host 9004 → container 9000) |
| `CLICKHOUSE_DATABASE` | `cryptolens` | |
| `CLICKHOUSE_USER` | `default` | |
| `CLICKHOUSE_PASSWORD` | `default` | |

---

## Commands (Makefile)

```bash
make up            # start all Docker services (Kafka, Schema Registry, Kafka UI, MinIO, Spark)
make down          # stop all services
make run           # run producer: uv run python -m cryptolens
make run-spark     # start spark-consumer container
make test          # pytest tests/ -v
make test-spark    # pytest tests/test_spark_consumer.py -v
make lint          # ruff check src/ tests/
make format        # ruff format src/ tests/
make logs          # kafka container logs
make logs-spark    # spark-consumer container logs
make minio-ui      # open MinIO console at http://localhost:9001
make ch-client     # connect to ClickHouse via clickhouse-client
make logs-ch       # clickhouse container logs
```

---

## Ports

| Service | Port | URL |
|---|---|---|
| Kafka | 9092 | `localhost:9092` |
| Schema Registry | 8081 | `http://localhost:8081` |
| Kafka UI | 8080 | `http://localhost:8080` |
| MinIO API | 9000 | `http://localhost:9000` |
| MinIO Console | 9001 | `http://localhost:9001` (user: minioadmin / minioadmin) |
| ClickHouse HTTP | 8123 | `http://localhost:8123` |
| ClickHouse Native | 9004 | `localhost:9004` (host) → container:9000 |

---

## Code Style

- PEP 8 strict, max 88 chars, enforced by `ruff`.
- Import order: stdlib → third-party → local (ruff isort).
- Type hints on **all** public function signatures.
- Docstrings on **all** public classes and methods.
- Log with `structlog.get_logger(__name__)`, use keyword arguments for context.
- Never use `print()` — use structured logging.

---

## Testing Conventions

- Tests live in `tests/`, mirrors `src/cryptolens/` structure.
- `test_parsing.py` — pure unit tests, no external deps.
- `test_serialization.py` — uses `fastavro` for Avro round-trips, no Kafka/Schema Registry needed.
- `test_spark_consumer.py` — uses local Spark (`master("local[1]")`), no Kafka/MinIO needed. Module-scoped `spark` fixture for performance.
- Never require running infrastructure in unit tests.

---

## Docker / Infrastructure Notes

- Kafka runs in **KRaft mode** (no ZooKeeper), `CLUSTER_ID` is fixed in docker-compose.yml.
- `kafka-data/` and `minio-data/` under `docker/` are runtime volumes — do not commit them.
- MinIO bucket `cryptolens` is auto-created by the `minio-init` one-shot container.
- Spark image is built from `docker/spark/Dockerfile` (base: `apache/spark:3.5.1`). Required JARs are downloaded at build time:
  - `spark-sql-kafka-0-10_2.12-3.5.1`
  - `spark-avro_2.12-3.5.1`
  - `hadoop-aws-3.3.4` + `aws-java-sdk-bundle-1.12.262`
  - `kafka-clients-3.4.0`, `commons-pool2-2.11.1`
- ClickHouse image: `clickhouse/clickhouse-server:25.3`. Schema initialized via `docker/clickhouse/initdb.d/01_schema.sql`.
  - `raw_trades_queue` — S3Queue engine, polls `s3://cryptolens/trades/**/*.parquet` in `unordered` mode (`ordered` requires ZooKeeper/Keeper coordination, use `unordered` for single-node).
  - `raw_trades` — MergeTree, ordered by `(symbol, trade_time, agg_trade_id)`.
  - `raw_trades_mv` — Materialized View converts Unix-ms → DateTime64(3) on ingestion. **Note:** in MV SELECT, `date`/`hour` reference the `trade_time` alias (already DateTime64), so use `toDate(trade_time, 'UTC')` directly — do NOT wrap in `fromUnixTimestamp64Milli(toInt64(...))` again (double-conversion gives wrong 1970 date).
  - Credentials: `default` / `default` (set via `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` env vars).
  - `docker/clickhouse/config.d/keeper.xml` — enables built-in ClickHouse Keeper (required for S3Queue).
  - `docker/clickhouse/config.d/network.xml` — sets `listen_host=0.0.0.0` (default is loopback-only, blocks host access).
  - Native TCP port mapped to host 9004 (avoids collision with MinIO 9000).
  - Runtime volume: `docker/clickhouse-data/` — do not commit.

---

## Planned Extensions (Future Work)

- Additional exchanges: abstract `BaseWSClient`.
- Additional data types: new `.avsc` + new WS stream.
- Prometheus + Grafana monitoring.
- VWAP / OHLCV aggregations in Spark.
