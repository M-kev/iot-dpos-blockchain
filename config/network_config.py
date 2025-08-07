from typing import Dict, List
import os
from dotenv import load_dotenv

load_dotenv()

# MQTT Broker Configuration
MQTT_BROKERS = [
    {
        "host": os.getenv("MQTT_BROKER_1_HOST", "192.168.2.10"),
        "port": int(os.getenv("MQTT_BROKER_1_PORT", "1883")),
        "username": os.getenv("MQTT_BROKER_1_USER", "broker1"),
        "password": os.getenv("MQTT_BROKER_1_PASS", "broker1pass"),
    },
    {
        "host": os.getenv("MQTT_BROKER_2_HOST", "192.168.2.11"),
        "port": int(os.getenv("MQTT_BROKER_2_PORT", "1883")),
        "username": os.getenv("MQTT_BROKER_2_USER", "broker2"),
        "password": os.getenv("MQTT_BROKER_2_PASS", "broker2pass"),
    }
]

# Raspberry Pi Node Configuration
RASPBERRY_PI_NODES = [
    {
        "id": "pi_node_1",
        "ip": os.getenv("PI_NODE_1_IP", "192.168.2.106"),
        "dashboard_port": 8001,
        "stake": 1000,
    },
    {
        "id": "pi_node_2",
        "ip": os.getenv("PI_NODE_2_IP", "192.168.2.107"),
        "dashboard_port": 8002,
        "stake": 1000,
    },
    {
        "id": "pi_node_3",
        "ip": os.getenv("PI_NODE_3_IP", "192.168.2.104"),
        "dashboard_port": 8003,
        "stake": 1000,
    },
    {
        "id": "pi_node_4",
        "ip": os.getenv("PI_NODE_4_IP", "192.168.2.102"),
        "dashboard_port": 8004,
        "stake": 1000,
    },
    {
        "id": "pi_node_5",
        "ip": os.getenv("PI_NODE_5_IP", "192.168.2.105"),
        "dashboard_port": 8005,
        "stake": 1000,
    },
    {
        "id": "pi_node_6",
        "ip": os.getenv("PI_NODE_6_IP", "192.168.2.101"),
        "dashboard_port": 8006,
        "stake": 1000,
    }
]

# MQTT Topics
MQTT_TOPICS = {
    "BLOCKS": "blocks",
    "TRANSACTIONS": "transactions",
    "METRICS": "metrics",
    "NETWORK_STATUS": "network/status",
    "VALIDATOR_STATUS": "validator/status"
}

# Raspberry Pi Specific Settings
RASPBERRY_PI_SETTINGS = {
    "cpu_throttle_temp": 80,  # Temperature in Celsius to start throttling
    "max_cpu_usage": 70,      # Maximum CPU usage percentage
    "max_memory_usage": 80,   # Maximum memory usage percentage
    "block_time": 3,          # Default block time in seconds
    "max_block_size": 1024,   # Maximum block size in bytes
    "sync_interval": 60,      # Blockchain sync interval in seconds
    "metrics_interval": 5,    # Metrics collection interval in seconds
}

# Network Settings
NETWORK_SETTINGS = {
    "max_peers": 5,           # Maximum number of peer connections
    "ping_interval": 30,      # Peer ping interval in seconds
    "timeout": 10,            # Network timeout in seconds
    "retry_attempts": 3,      # Number of retry attempts for failed operations
}

def get_node_config(node_id: str) -> Dict:
    """Get configuration for a specific node."""
    for node in RASPBERRY_PI_NODES:
        if node["id"] == node_id:
            return node
    return {}

def get_broker_config(broker_index: int) -> Dict:
    """Get configuration for a specific MQTT broker."""
    if 0 <= broker_index < len(MQTT_BROKERS):
        return MQTT_BROKERS[broker_index]
    return {} 