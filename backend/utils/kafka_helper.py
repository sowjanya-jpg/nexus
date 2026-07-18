import json
import os
from typing import Dict, Any
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")

def get_kafka_producer() -> Producer:
    """
    Get configured Kafka Producer.
    """
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'client.id': 'nexus-backend-producer'
    }
    return Producer(conf)

def init_kafka_topics(topics=None):
    """
    Initialize Kafka topics if they do not exist.
    """
    if topics is None:
        topics = ["iot-sensor-stream", "production-events"]
        
    conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}
    admin_client = AdminClient(conf)
    
    new_topics = []
    # Fetch existing topics
    try:
        metadata = admin_client.list_topics(timeout=5.0)
        existing_topics = metadata.topics.keys()
    except Exception as e:
        print(f"Warning: Could not connect to Kafka Broker to check/initialize topics. Error: {e}")
        return False
        
    for topic in topics:
        if topic not in existing_topics:
            new_topics.append(NewTopic(topic, num_partitions=1, replication_factor=1))
            
    if new_topics:
        futures = admin_client.create_topics(new_topics)
        for topic_name, future in futures.items():
            try:
                future.result()
                print(f"Kafka Topic '{topic_name}' created successfully.")
            except Exception as e:
                print(f"Failed to create topic '{topic_name}': {e}")
    else:
        print("All required Kafka topics already exist.")
    return True

def produce_message(topic: str, message: Dict[str, Any]):
    """
    Publish JSON message to Kafka topic.
    """
    try:
        producer = get_kafka_producer()
        payload = json.dumps(message).encode('utf-8')
        
        def delivery_report(err, msg):
            if err is not None:
                print(f"Message delivery failed: {err}")
            else:
                print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

        producer.produce(topic, value=payload, callback=delivery_report)
        producer.flush(1.0) # Wait up to 1 second to flush queue
    except Exception as e:
        print(f"Failed to send message to Kafka: {e}")
        # In a real environment, we'd queue locally or handle drift, but we proceed for demo stability
