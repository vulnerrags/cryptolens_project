"""Unit tests for the PySpark Structured Streaming consumer.

All tests run in local Spark mode (no Kafka or MinIO required).
The SparkSession fixture is module-scoped so it is created once per session.
"""

import io
import json
import struct
from pathlib import Path

import fastavro
import pytest

_SCHEMA_PATH = (
    Path(__file__).parent.parent / "src" / "cryptolens" / "schemas" / "trade.avsc"
)

_VALID_RECORD = {
    "symbol": "BTCUSDT",
    "agg_trade_id": 9876543,
    "price": "42000.00",
    "quantity": "0.01500",
    "first_trade_id": 100000,
    "last_trade_id": 100005,
    # 2024-01-15 15:30:00 UTC in ms
    "trade_time": 1705332600000,
    "is_buyer_maker": False,
    "ingestion_time": 1705332601000,
}


@pytest.fixture(scope="module")
def spark():
    """Return a local SparkSession, shut it down after the test module."""
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[1]")
        .appName("test-cryptolens-consumer")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


# ---------------------------------------------------------------------------
# Test 1: stripping the 5-byte Confluent wire-format prefix
# ---------------------------------------------------------------------------


def test_strip_confluent_prefix(spark) -> None:
    """substring(value, 6, ...) must remove the 5-byte Confluent header."""
    from pyspark.sql.functions import expr
    from pyspark.sql.types import BinaryType, StructField, StructType

    # Build a fake Confluent wire-format byte string:
    # magic byte (0x00) + schema ID (big-endian int 1) + arbitrary payload
    schema_id = struct.pack(">I", 1)  # 4 bytes big-endian
    prefix = b"\x00" + schema_id      # 5 bytes total
    payload = b"\x0cBTCUSDT"          # arbitrary Avro-like bytes

    wire_bytes = bytearray(prefix + payload)

    schema = StructType([StructField("value", BinaryType())])
    df = spark.createDataFrame([(wire_bytes,)], schema)

    result = df.select(
        expr("substring(value, 6, length(value) - 5)").alias("avro")
    ).collect()

    assert bytes(result[0]["avro"]) == payload


# ---------------------------------------------------------------------------
# Test 2: partition column derivation from trade_time
# ---------------------------------------------------------------------------


def test_partition_columns(spark) -> None:
    """date and hour columns must be derived correctly from trade_time (ms UTC)."""
    from pyspark.sql.functions import col, date_format, to_date
    from pyspark.sql.types import LongType, StructField, StructType

    from cryptolens.spark.consumer import _add_partition_columns

    # 2024-01-15 15:30:00 UTC → date=2024-01-15, hour=15
    trade_time_ms = 1705332600000

    schema = StructType([StructField("trade_time", LongType())])
    df = spark.createDataFrame([(trade_time_ms,)], schema)

    result = _add_partition_columns(df).collect()

    row = result[0]
    assert str(row["date"]) == "2024-01-15"
    assert row["hour"] == 15


# ---------------------------------------------------------------------------
# Test 3: Avro schema is parseable by from_avro
# ---------------------------------------------------------------------------


def test_avro_schema_loads(spark) -> None:
    """from_avro must accept the trade.avsc schema string without errors."""
    from pyspark.sql.avro.functions import from_avro
    from pyspark.sql.functions import expr
    from pyspark.sql.types import BinaryType, StructField, StructType

    from cryptolens.spark.consumer import _load_avro_schema

    avro_schema_str = _load_avro_schema()

    # Empty bytes will not decode correctly, but from_avro should not raise
    # a schema-parsing error — only a data error, which we catch via options.
    schema = StructType([StructField("value", BinaryType())])
    df = spark.createDataFrame([(bytearray(b""),)], schema)

    options = {"mode": "PERMISSIVE"}
    rows = df.select(
        from_avro(expr("value"), avro_schema_str, options).alias("trade")
    ).collect()

    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Test 4: full Avro round-trip through the 5-byte-strip + from_avro path
# ---------------------------------------------------------------------------


def test_full_avro_roundtrip(spark) -> None:
    """A fastavro-serialised trade (with Confluent prefix) must decode correctly."""
    from pyspark.sql.types import BinaryType, StructField, StructType

    from cryptolens.spark.consumer import _decode_trades, _load_avro_schema

    avro_schema_str = _load_avro_schema()
    parsed_schema = fastavro.parse_schema(json.loads(avro_schema_str))

    # Serialize with fastavro (schemaless — no file header)
    buf = io.BytesIO()
    fastavro.schemaless_writer(buf, parsed_schema, _VALID_RECORD)
    raw_avro = buf.getvalue()

    # Prepend 5-byte Confluent wire-format prefix
    prefix = b"\x00" + struct.pack(">I", 1)
    wire_bytes = bytearray(prefix + raw_avro)

    schema = StructType([StructField("value", BinaryType())])
    df = spark.createDataFrame([(wire_bytes,)], schema)

    decoded = _decode_trades(df, avro_schema_str).collect()

    assert len(decoded) == 1
    row = decoded[0].asDict()
    assert row["symbol"] == _VALID_RECORD["symbol"]
    assert row["agg_trade_id"] == _VALID_RECORD["agg_trade_id"]
    assert row["price"] == _VALID_RECORD["price"]
    assert row["quantity"] == _VALID_RECORD["quantity"]
    assert row["trade_time"] == _VALID_RECORD["trade_time"]
    assert row["is_buyer_maker"] == _VALID_RECORD["is_buyer_maker"]
    assert row["ingestion_time"] == _VALID_RECORD["ingestion_time"]
