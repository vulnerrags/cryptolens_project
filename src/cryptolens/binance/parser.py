"""Parser for Binance WebSocket stream messages."""

import time


def parse_trade(raw: dict) -> dict:
    """Map a Binance combined stream aggTrade payload to the Trade Avro schema dict.

    Binance combined stream wraps each event as::

        {"stream": "btcusdt@aggTrade", "data": { ... }}

    The inner ``data`` object fields are documented at:
    https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams#aggregate-trade-streams

    Args:
        raw: The parsed JSON object received from the WebSocket.

    Returns:
        A dict whose keys match the Trade Avro schema fields.
    """
    data = raw["data"]

    return {
        "symbol": data["s"],
        "agg_trade_id": data["a"],
        "price": data["p"],
        "quantity": data["q"],
        "first_trade_id": data["f"],
        "last_trade_id": data["l"],
        "trade_time": data["T"],
        "is_buyer_maker": data["m"],
        "ingestion_time": int(time.time() * 1000),
    }
