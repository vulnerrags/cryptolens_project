FROM apache/spark:3.5.1

USER root

# Download JARs required for Kafka + Avro + S3A (MinIO) support.
# hadoop-aws:3.3.4 + aws-java-sdk-bundle:1.12.262 is the stable pair for
# Spark 3.5.1 which ships with Hadoop 3.3.4 internally.
RUN curl -fL -o /opt/spark/jars/spark-sql-kafka-0-10_2.12-3.5.1.jar \
      https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.1/spark-sql-kafka-0-10_2.12-3.5.1.jar && \
    curl -fL -o /opt/spark/jars/spark-token-provider-kafka-0-10_2.12-3.5.1.jar \
      https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.1/spark-token-provider-kafka-0-10_2.12-3.5.1.jar && \
    curl -fL -o /opt/spark/jars/spark-avro_2.12-3.5.1.jar \
      https://repo1.maven.org/maven2/org/apache/spark/spark-avro_2.12/3.5.1/spark-avro_2.12-3.5.1.jar && \
    curl -fL -o /opt/spark/jars/hadoop-aws-3.3.4.jar \
      https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -fL -o /opt/spark/jars/aws-java-sdk-bundle-1.12.262.jar \
      https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    curl -fL -o /opt/spark/jars/kafka-clients-3.4.0.jar \
      https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.0/kafka-clients-3.4.0.jar && \
    curl -fL -o /opt/spark/jars/commons-pool2-2.11.1.jar \
      https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar

COPY src/cryptolens/spark/consumer.py /app/consumer.py
COPY src/cryptolens/schemas/trade.avsc /app/trade.avsc

USER spark

CMD ["/opt/spark/bin/spark-submit", "--master", "local[2]", "/app/consumer.py"]
