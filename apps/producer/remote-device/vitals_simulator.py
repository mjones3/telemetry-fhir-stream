import os
import time
import json
import random
import math
import uuid
from datetime import datetime, timezone
from kafka import KafkaProducer
import time
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

# Kafka Configuration
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'vitals')
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9093')
NUM_PARTITIONS = int(os.getenv('NUM_PARTITIONS', 10))
NUM_DEVICES = int(os.getenv('NUM_DEVICES', 4))  # Devices per container instance

# Generate random device and patient IDs for this container
devices = [
    {
        'device_id': str(uuid.uuid4()),
        'patient_id': str(uuid.uuid4()),
        'baseline_hr': random.randint(60, 80),
        'baseline_systolic': random.randint(110, 120),
        'baseline_diastolic': random.randint(70, 80)
    }
    for _ in range(NUM_DEVICES)
]


def get_partition(device_id):
    """
    Partitioning strategy based on device_id hash modulo number of partitions.
    Ensures messages from the same device go to the same partition.
    """
    return hash(device_id) % NUM_PARTITIONS

def create_topic(broker, topic_name, num_partitions=NUM_PARTITIONS, replication_factor=1):
    admin_client = KafkaAdminClient(bootstrap_servers=broker)
    topic_list = [NewTopic(name=topic_name, num_partitions=num_partitions, replication_factor=replication_factor)]
    try:
        admin_client.create_topics(new_topics=topic_list, validate_only=False)
        print(f"Topic '{topic_name}' created with {num_partitions} partitions.")
    except TopicAlreadyExistsError:
        print(f"Topic '{topic_name}' already exists.")

def generate_vitals(device, t):
    # Sinusoidal wave with random jitter for each vital
    hr = device['baseline_hr'] + 5 * math.sin(0.1 * t) + random.uniform(-2, 2)
    systolic = device['baseline_systolic'] + 3 * math.sin(0.07 * t) + random.uniform(-1, 1)
    diastolic = device['baseline_diastolic'] + 2 * math.sin(0.05 * t) + random.uniform(-1, 1)

    timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    return {
        'device_id': device['device_id'],
        'patient_id': device['patient_id'],
        'timestamp': timestamp,
        'heart_rate': round(hr, 1),
        'systolic_bp': round(systolic, 1),
        'diastolic_bp': round(diastolic, 1)
    }


def wait_for_kafka(broker, timeout=60, retry_interval=2):
    """Wait for the Kafka broker to become available."""
    start_time = time.time()
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"Connected to Kafka broker at {broker}")
            return producer
        except NoBrokersAvailable:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Kafka broker at {broker} not available after {timeout} seconds.")
            print(f"Kafka broker at {broker} not available, retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)
            retry_interval = min(retry_interval * 2, 10)  # exponential backoff, max 10 seconds
                                                                                                                                                                                                                                                                                             
def main():

    producer = wait_for_kafka(KAFKA_BROKER)
    create_topic(KAFKA_BROKER, KAFKA_TOPIC, num_partitions=NUM_PARTITIONS)
    
    t = 0
    while True:
        start_time = time.time()
        for device in devices:
            vitals = generate_vitals(device, t)
            partition = get_partition(device['device_id'])
            producer.send(KAFKA_TOPIC, value=vitals, partition=partition)
            print(f"Sent: {vitals} to partition {partition}")
        t += 1
        elapsed = time.time() - start_time
        sleep_time = max(0, 1 - elapsed)
        time.sleep(sleep_time)


if __name__ == '__main__':
    main()
