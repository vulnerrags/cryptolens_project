"""Kafka producer wrapper using Avro serialization via Confluent Schema Registry."""

from pathlib import Path

import structlog
from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer

from cryptolens.config import Settings

log = structlog.get_logger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "trade.avsc"


class TradeProducer:
    """Kafka producer that serializes trade records using Avro and Schema Registry."""

    def __init__(self, config: Settings) -> None:
        """Initialize the producer and register the Avro schema.

        Args:
            config: Application settings with Kafka and Schema Registry URLs.
        """
        schema_registry_client = SchemaRegistryClient(
            {"url": config.schema_registry_url}
        )
        schema_str = _SCHEMA_PATH.read_text(encoding="utf-8")
        avro_serializer = AvroSerializer(schema_registry_client, schema_str)

        self._producer = SerializingProducer(
            {
                "bootstrap.servers": config.kafka_bootstrap_servers,
                "key.serializer": StringSerializer("utf_8"),
                "value.serializer": avro_serializer,
            }
        )

    def produce(self, topic: str, key: str, value: dict) -> None:
        """Enqueue a message for delivery to Kafka.

        Calls poll(0) after enqueuing to trigger any pending delivery callbacks
        without blocking.

        Args:
            topic: Target Kafka topic name.
            key: Message key (used for partition assignment).
            value: Message payload as a dict matching the Avro schema.
        """
        self._producer.produce(
            topic=topic,
            key=key,
            value=value,
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def flush(self) -> None:
        """Block until all enqueued messages have been delivered or failed."""
        self._producer.flush()

    def _on_delivery(self, err: Exception | None, msg: object) -> None:
        """Handle delivery acknowledgement from the broker.

        Args:
            err: Delivery error, or None on success.
            msg: The delivered message object.
        """
        if err is not None:
            log.error("delivery_failed", error=str(err))
        else:
            log.debug("delivered", topic=msg.topic(), offset=msg.offset())
