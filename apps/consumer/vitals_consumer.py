from kafka import KafkaConsumer
from influxdb_client import InfluxDBClient, Point, WritePrecision
import json
import os
import time
from influxdb_client.client.write_api import SYNCHRONOUS

# Kafka Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'vitals')
KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'telemetry-consumer-group')

# InfluxDB Configuration
INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN', 'my-token')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'my-org')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'vitals')


def wait_for_kafka(max_retries=10, delay=5):
    attempt = 0
    while attempt < max_retries:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=[KAFKA_BROKER],
                auto_offset_reset='earliest',
                group_id=KAFKA_GROUP_ID,
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            print(f"Connected to Kafka broker at {KAFKA_BROKER}")
            return consumer
        except Exception as e:
            attempt += 1
            print(f"Kafka broker not available yet (attempt {attempt}/{max_retries}). Retrying in {delay} seconds...")
            time.sleep(delay)
    raise Exception(f"Failed to connect to Kafka broker after {max_retries} attempts.")


def main():
    consumer = wait_for_kafka()

    # Connect to InfluxDB
    influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    for message in consumer:
        vitals = message.value
        point = Point("vitals") \
            .tag("device_id", vitals['device_id']) \
            .tag("patient_id", vitals['patient_id']) \
            .field("heart_rate", vitals['heart_rate']) \
            .field("systolic_bp", vitals['systolic_bp']) \
            .field("diastolic_bp", vitals['diastolic_bp']) \
            .time(vitals['timestamp'], WritePrecision.NS)
        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
        print(f"Wrote point: {point}")


if __name__ == '__main__':
    main()
