"""PySpark Structured Streaming consumer.

Reads raw Avro-encoded trades from the crypto.trades Kafka topic,
deserializes them (stripping the 5-byte Confluent wire-format prefix),
and writes Parquet files (Snappy) to MinIO partitioned by symbol/date/hour.

Configuration is read entirely from environment variables so that this
module can run inside a Docker container without the rest of the
cryptolens Python package installed.
"""

import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.functions import col, date_format, expr, to_date
from pyspark.sql.streaming import StreamingQuery

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.environ.get(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
)
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC_TRADES", "crypto.trades")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "cryptolens")
SPARK_TRIGGER_SECONDS = int(os.environ.get("SPARK_TRIGGER_SECONDS", "30"))

# Avro schema file is copied into /app/trade.avsc by the Dockerfile.
# When running locally for tests, resolve relative to this file.
_SCHEMA_PATH = Path(os.environ.get("AVRO_SCHEMA_PATH", "/app/trade.avsc"))
if not _SCHEMA_PATH.exists():
    _SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "trade.avsc"


def _load_avro_schema() -> str:
    """Return the Avro schema as a JSON string for use with from_avro()."""
    return _SCHEMA_PATH.read_text(encoding="utf-8")


def _create_spark_session() -> SparkSession:
    """Build and return a configured SparkSession."""
    return (
        SparkSession.builder.appName("cryptolens-trade-consumer")
        # Ensure deterministic UTC-based partition paths
        .config("spark.sql.session.timeZone", "UTC")
        # Avoid creating 200 tiny Parquet files per micro-batch on a single node
        .config("spark.sql.shuffle.partitions", "4")
        # S3A / MinIO settings
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        # path-style access is required for MinIO (virtual-hosted style not supported)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config(
            "spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        # MinIO runs over plain HTTP in the local Docker setup
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .getOrCreate()
    )


def _read_stream(spark: SparkSession) -> DataFrame:
    """Open a streaming DataFrame from the Kafka topic."""
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )


def _decode_trades(raw_df: DataFrame, avro_schema_str: str) -> DataFrame:
    """Deserialize Confluent Avro bytes into a structured DataFrame.

    The Confluent wire format prepends 5 bytes before the Avro payload:
      byte 0:    magic byte (0x00)
      bytes 1-4: schema ID (big-endian int)
    PySpark's from_avro() expects raw Avro bytes, so we strip the prefix.
    substring() in Spark SQL is 1-indexed.
    """
    avro_bytes = expr("substring(value, 6, length(value) - 5)")
    return raw_df.select(
        from_avro(avro_bytes, avro_schema_str).alias("trade")
    ).select("trade.*")


def _add_partition_columns(df: DataFrame) -> DataFrame:
    """Derive date and hour partition columns from trade_time (Unix epoch ms, UTC)."""
    return (
        df.withColumn("trade_ts", (col("trade_time") / 1000).cast("timestamp"))
        .withColumn("date", to_date(col("trade_ts")))
        .withColumn("hour", date_format(col("trade_ts"), "HH").cast("int"))
        .drop("trade_ts")
    )


def _write_stream(df: DataFrame) -> StreamingQuery:
    """Configure and start the writeStream to MinIO."""
    output_path = f"s3a://{MINIO_BUCKET}/trades/"
    checkpoint_path = f"s3a://{MINIO_BUCKET}/checkpoints/trades/"

    return (
        df.writeStream.format("parquet")
        .option("path", output_path)
        .option("checkpointLocation", checkpoint_path)
        .option("compression", "snappy")
        .partitionBy("symbol", "date", "hour")
        .trigger(processingTime=f"{SPARK_TRIGGER_SECONDS} seconds")
        .start()
    )


def run() -> None:
    """Start the Spark Structured Streaming job and block until termination."""
    spark = _create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    avro_schema_str = _load_avro_schema()

    raw_df = _read_stream(spark)
    decoded_df = _decode_trades(raw_df, avro_schema_str)
    partitioned_df = _add_partition_columns(decoded_df)
    query = _write_stream(partitioned_df)
    query.awaitTermination()


if __name__ == "__main__":
    run()
