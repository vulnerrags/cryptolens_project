"""Unit tests for Avro schema serialization round-trips using fastavro.

These tests validate the trade.avsc schema without requiring a running
Schema Registry or Kafka broker.
"""

import io
import json
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
    "trade_time": 1700000000000,
    "is_buyer_maker": False,
    "ingestion_time": 1700000001000,
}


@pytest.fixture(scope="module")
def parsed_schema() -> dict:
    """Return the parsed fastavro schema object."""
    raw = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return fastavro.parse_schema(raw)


def _roundtrip(schema: dict, record: dict) -> dict:
    """Serialize then deserialize *record* using *schema* and return the result."""
    buf = io.BytesIO()
    fastavro.schemaless_writer(buf, schema, record)
    buf.seek(0)
    return fastavro.schemaless_reader(buf, schema)


def test_valid_record_roundtrip(parsed_schema: dict) -> None:
    result = _roundtrip(parsed_schema, _VALID_RECORD)
    assert result == _VALID_RECORD


def test_roundtrip_buyer_maker_true(parsed_schema: dict) -> None:
    record = {**_VALID_RECORD, "is_buyer_maker": True}
    result = _roundtrip(parsed_schema, record)
    assert result["is_buyer_maker"] is True


def test_roundtrip_preserves_string_price(parsed_schema: dict) -> None:
    """Price must remain a string; numeric precision must not be altered."""
    record = {**_VALID_RECORD, "price": "99999.99000000"}
    result = _roundtrip(parsed_schema, record)
    assert result["price"] == "99999.99000000"


def test_roundtrip_ethusdt(parsed_schema: dict) -> None:
    record = {
        "symbol": "ETHUSDT",
        "agg_trade_id": 1234567,
        "price": "2200.50",
        "quantity": "0.50000",
        "first_trade_id": 200000,
        "last_trade_id": 200003,
        "trade_time": 1700000000500,
        "is_buyer_maker": True,
        "ingestion_time": 1700000001500,
    }
    result = _roundtrip(parsed_schema, record)
    assert result == record


def test_missing_required_field_raises(parsed_schema: dict) -> None:
    """Serialization must fail if a required field is absent."""
    incomplete = {k: v for k, v in _VALID_RECORD.items() if k != "symbol"}
    with pytest.raises(Exception):
        _roundtrip(parsed_schema, incomplete)
