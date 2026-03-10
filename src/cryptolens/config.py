"""Application configuration loaded from environment variables or .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables or from a .env file
    in the current working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    kafka_bootstrap_servers: str = "localhost:9092"
    schema_registry_url: str = "http://localhost:8081"
    binance_ws_base_url: str = "wss://stream.binance.com:9443/stream"
    symbols: list[str] = ["BTCUSDT", "ETHUSDT"]
    kafka_topic_trades: str = "crypto.trades"
    log_level: str = "INFO"

    # MinIO / S3-compatible storage
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "cryptolens"

    # Spark consumer
    spark_trigger_seconds: int = 30
    spark_checkpoint_dir: str = "s3a://cryptolens/checkpoints/trades"

    # ClickHouse
    clickhouse_host: str = "localhost"
    clickhouse_http_port: int = 8123
    clickhouse_native_port: int = 9004
    clickhouse_database: str = "cryptolens"
    clickhouse_user: str = "default"
    clickhouse_password: str = "default"

    @property
    def binance_ws_url(self) -> str:
        """Build the Binance combined WebSocket stream URL from configured symbols."""
        streams = "/".join(f"{symbol.lower()}@aggTrade" for symbol in self.symbols)
        return f"{self.binance_ws_base_url}?streams={streams}"
