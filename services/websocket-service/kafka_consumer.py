# kafka_consumer.py
from kafka import KafkaConsumer
import json

def create_consumer():
    return KafkaConsumer(
        "eta-topic",
        bootstrap_servers="localhost:9092",
        value_deserializer=lambda m: json.loads(m.decode("utf-8"))
    )