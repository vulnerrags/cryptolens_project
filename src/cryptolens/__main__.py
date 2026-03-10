"""Entry point for the CryptoLens producer.

Run with:
    python -m cryptolens
or:
    uv run python -m cryptolens
"""

import signal

import structlog

from cryptolens.binance.client import BinanceWSClient
from cryptolens.config import Settings
from cryptolens.kafka.producer import TradeProducer
from cryptolens.logging import configure_logging

log = structlog.get_logger(__name__)


def main() -> None:
    """Bootstrap configuration, producer, and WebSocket client, then start streaming."""
    config = Settings()
    configure_logging(config.log_level)

    log.info(
        "starting",
        symbols=config.symbols,
        topic=config.kafka_topic_trades,
        kafka=config.kafka_bootstrap_servers,
    )

    producer = TradeProducer(config)
    client = BinanceWSClient(config, producer)

    signal.signal(signal.SIGINT, lambda *_: client.stop())
    signal.signal(signal.SIGTERM, lambda *_: client.stop())

    try:
        client.run()
    finally:
        log.info("shutting_down")
        producer.flush()


if __name__ == "__main__":
    main()
