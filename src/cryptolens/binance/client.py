"""Binance WebSocket client with automatic reconnection."""

import json
import random
import time

import structlog
import websocket

from cryptolens.binance.parser import parse_trade
from cryptolens.config import Settings
from cryptolens.kafka.producer import TradeProducer

log = structlog.get_logger(__name__)

# Reconnect backoff parameters
_INITIAL_BACKOFF_SECONDS: float = 1.0
_MAX_BACKOFF_SECONDS: float = 60.0
# If the connection lived longer than this, consider it healthy and reset backoff.
_HEALTHY_CONNECTION_SECONDS: float = 5.0

# websocket-client ping settings to satisfy Binance keepalive requirements.
# Binance sends a ping every 20 s and disconnects if no pong is received within 60 s.
_PING_INTERVAL_SECONDS: int = 20
_PING_TIMEOUT_SECONDS: int = 10


class BinanceWSClient:
    """Synchronous Binance WebSocket client.

    Connects to the Binance combined aggTrade stream for the configured symbols,
    parses each message, and forwards the resulting trade dict to the Kafka producer.

    Reconnection is handled automatically with exponential backoff and jitter.
    Binance forcibly closes connections after ~24 hours; the reconnect loop handles
    this transparently.
    """

    def __init__(self, config: Settings, producer: TradeProducer) -> None:
        """Initialise the client.

        Args:
            config: Application settings (WebSocket URL, topic name, etc.).
            producer: Kafka producer used to forward parsed trade events.
        """
        self._url = config.binance_ws_url
        self._topic = config.kafka_topic_trades
        self._producer = producer
        self._stopped = False
        self._ws: websocket.WebSocketApp | None = None

    def run(self) -> None:
        """Start the WebSocket receive loop.

        Blocks the calling thread until :meth:`stop` is called.  Reconnects
        automatically on any disconnect using exponential backoff with jitter.
        """
        backoff = _INITIAL_BACKOFF_SECONDS

        while not self._stopped:
            connected_at = time.monotonic()

            self._ws = websocket.WebSocketApp(
                self._url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            self._ws.run_forever(
                ping_interval=_PING_INTERVAL_SECONDS,
                ping_timeout=_PING_TIMEOUT_SECONDS,
            )

            if self._stopped:
                break

            elapsed = time.monotonic() - connected_at
            if elapsed >= _HEALTHY_CONNECTION_SECONDS:
                backoff = _INITIAL_BACKOFF_SECONDS
            else:
                sleep_duration = backoff + random.uniform(0, 1)
                log.warning(
                    "ws_reconnect",
                    retry_in=round(sleep_duration, 1),
                    backoff=backoff,
                )
                time.sleep(sleep_duration)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

    def stop(self) -> None:
        """Signal the client to stop and close the active WebSocket connection."""
        self._stopped = True
        if self._ws is not None:
            self._ws.close()

    # ------------------------------------------------------------------
    # WebSocketApp callbacks
    # ------------------------------------------------------------------

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        log.info("ws_connected", url=self._url)

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        """Parse an incoming message and forward it to Kafka.

        Args:
            ws: The active WebSocketApp instance (unused).
            message: Raw JSON string received from Binance.
        """
        try:
            raw = json.loads(message)
            trade = parse_trade(raw)
            self._producer.produce(
                topic=self._topic,
                key=trade["symbol"],
                value=trade,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("message_processing_failed", error=str(exc))

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        log.error("ws_error", error=str(error))

    def _on_close(
        self,
        ws: websocket.WebSocketApp,
        close_status_code: int | None,
        close_msg: str | None,
    ) -> None:
        log.info("ws_closed", code=close_status_code, message=close_msg)
