"""Unit tests for Binance WebSocket message parsing."""

import pytest

from cryptolens.binance.parser import parse_trade

_BTCUSDT_FIXTURE = {
    "stream": "btcusdt@aggTrade",
    "data": {
        "e": "aggTrade",
        "E": 1700000001234,
        "s": "BTCUSDT",
        "a": 9876543,
        "p": "42000.00",
        "q": "0.01500",
        "f": 100000,
        "l": 100005,
        "T": 1700000000000,
        "m": False,
    },
}

_ETHUSDT_FIXTURE = {
    "stream": "ethusdt@aggTrade",
    "data": {
        "e": "aggTrade",
        "E": 1700000001234,
        "s": "ETHUSDT",
        "a": 1234567,
        "p": "2200.50",
        "q": "0.50000",
        "f": 200000,
        "l": 200003,
        "T": 1700000000500,
        "m": True,
    },
}


def test_parse_trade_symbol() -> None:
    result = parse_trade(_BTCUSDT_FIXTURE)
    assert result["symbol"] == "BTCUSDT"


def test_parse_trade_all_schema_fields_present() -> None:
    expected_fields = {
        "symbol",
        "agg_trade_id",
        "price",
        "quantity",
        "first_trade_id",
        "last_trade_id",
        "trade_time",
        "is_buyer_maker",
        "ingestion_time",
    }
    result = parse_trade(_BTCUSDT_FIXTURE)
    assert set(result.keys()) == expected_fields


def test_parse_trade_field_types() -> None:
    result = parse_trade(_BTCUSDT_FIXTURE)

    assert isinstance(result["symbol"], str)
    assert isinstance(result["agg_trade_id"], int)
    assert isinstance(result["price"], str)
    assert isinstance(result["quantity"], str)
    assert isinstance(result["first_trade_id"], int)
    assert isinstance(result["last_trade_id"], int)
    assert isinstance(result["trade_time"], int)
    assert isinstance(result["is_buyer_maker"], bool)
    assert isinstance(result["ingestion_time"], int)


def test_parse_trade_values() -> None:
    result = parse_trade(_BTCUSDT_FIXTURE)

    assert result["agg_trade_id"] == 9876543
    assert result["price"] == "42000.00"
    assert result["quantity"] == "0.01500"
    assert result["first_trade_id"] == 100000
    assert result["last_trade_id"] == 100005
    assert result["trade_time"] == 1700000000000
    assert result["is_buyer_maker"] is False


def test_parse_trade_ingestion_time_is_recent() -> None:
    import time

    before = int(time.time() * 1000)
    result = parse_trade(_BTCUSDT_FIXTURE)
    after = int(time.time() * 1000)

    assert before <= result["ingestion_time"] <= after


@pytest.mark.parametrize(
    "fixture",
    [_BTCUSDT_FIXTURE, _ETHUSDT_FIXTURE],
    ids=["BTCUSDT", "ETHUSDT"],
)
def test_parse_trade_multiple_symbols(fixture: dict) -> None:
    result = parse_trade(fixture)
    assert result["symbol"] in {"BTCUSDT", "ETHUSDT"}
    assert result["agg_trade_id"] > 0
