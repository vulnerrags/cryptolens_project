-- CryptoLens ClickHouse schema
-- S3Queue (ordered) reads Parquet files written by Spark from MinIO.
-- Partition columns (symbol, date, hour) are Hive-style path segments,
-- not stored inside the Parquet file — use_hive_partitioning extracts them.

CREATE DATABASE IF NOT EXISTS cryptolens;

-- ── 1. S3Queue source table ────────────────────────────────────────────────
-- Polls s3://cryptolens/trades/**/*.parquet in ordered mode.
-- Ordered mode remembers the last processed file per shard and resumes
-- from that position after restarts, so every file is processed exactly once.
CREATE TABLE IF NOT EXISTS cryptolens.raw_trades_queue
(
    agg_trade_id    Int64,
    price           String,
    quantity        String,
    first_trade_id  Int64,
    last_trade_id   Int64,
    trade_time      Int64,   -- Unix epoch milliseconds (Avro long)
    is_buyer_maker  Bool,
    ingestion_time  Int64    -- Unix epoch milliseconds (Avro long)
    -- symbol/date/hour are Hive path segments, not in the Parquet file;
    -- extracted in the Materialized View via _path virtual column.
)
ENGINE = S3Queue(
    'http://minio:9000/cryptolens/trades/**/*.parquet',
    'minioadmin',
    'minioadmin',
    'Parquet'
)
SETTINGS
    mode = 'unordered';

-- ── 2. MergeTree storage table ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cryptolens.raw_trades
(
    symbol          LowCardinality(String),
    agg_trade_id    Int64,
    price           String,
    quantity        String,
    first_trade_id  Int64,
    last_trade_id   Int64,
    trade_time      DateTime64(3, 'UTC'),    -- converted from Unix ms
    is_buyer_maker  Bool,
    ingestion_time  DateTime64(3, 'UTC'),    -- converted from Unix ms
    `date`          Date,
    hour            UInt8
)
ENGINE = MergeTree()
PARTITION BY (symbol, toYYYYMM(trade_time))
ORDER BY (symbol, trade_time, agg_trade_id);

-- ── 3. Materialized View: S3Queue → MergeTree ──────────────────────────────
-- Fires automatically for each batch read by the S3Queue background thread.
-- Converts Unix-ms integers to DateTime64 on the way in.
-- symbol/date/hour are not in the Parquet file (Hive-style path segments),
-- so they are extracted from the _path virtual column via regex.
CREATE MATERIALIZED VIEW IF NOT EXISTS cryptolens.raw_trades_mv
TO cryptolens.raw_trades
AS
SELECT
    extract(_path, 'symbol=([^/]+)')                   AS symbol,
    agg_trade_id,
    price,
    quantity,
    first_trade_id,
    last_trade_id,
    fromUnixTimestamp64Milli(toInt64(trade_time))               AS trade_time,
    is_buyer_maker,
    fromUnixTimestamp64Milli(toInt64(ingestion_time))           AS ingestion_time,
    toDate(trade_time, 'UTC')                                    AS `date`,
    toHour(trade_time, 'UTC')                                    AS hour
FROM cryptolens.raw_trades_queue;
