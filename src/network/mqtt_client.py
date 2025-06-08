# ... existing code from src/mqtt/client.py ... 

import paho.mqtt.client as mqtt
import json
from typing import Callable, Dict, Any, Optional, List
import time
import threading
from config.network_config import MQTT_BROKERS, MQTT_TOPICS, NETWORK_SETTINGS

class MQTTClient:
    def __init__(self, client_id: str, node_config: Dict[str, Any]):
        self.client_id = client_id
        self.node_config = node_config
        self.clients: List[mqtt.Client] = []
        self.connected = False
        self.message_handlers: Dict[str, Callable] = {}
        self.active_broker_index = 0
        self._setup_clients()
        
    def _setup_clients(self) -> None:
        """Setup MQTT clients for each broker."""
        for broker in MQTT_BROKERS:
            client = mqtt.Client(f"{self.client_id}_{broker['host']}")
            client.on_connect = self._on_connect
            client.on_message = self._on_message
            client.on_disconnect = self._on_disconnect
            
            if broker.get('username'):
                client.username_pw_set(
                    broker['username'],
                    broker.get('password', '')
                )
                
            self.clients.append(client)
            
    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Handle connection callback."""
        if rc == 0:
            self.connected = True
            print(f"Connected to MQTT broker at {client._host}")
            
            # Subscribe to topics
            for topic in MQTT_TOPICS.values():
                client.subscribe(topic)
        else:
            print(f"Failed to connect to MQTT broker, return code: {rc}")
            
    def _on_message(self, client, userdata, msg) -> None:
        """Handle incoming message callback."""
        print(f"[MQTT] Received message on topic '{msg.topic}'")
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            if topic in self.message_handlers:
                print(f"[MQTT] Routing message from topic '{topic}' to handler.")
                self.message_handlers[topic](payload)
            else:
                print(f"[MQTT] No handler registered for topic '{topic}'.")
        except json.JSONDecodeError:
            print(f"[MQTT] Failed to decode message: {msg.payload}")
            
    def _on_disconnect(self, client, userdata, rc) -> None:
        """Handle disconnection callback."""
        self.connected = False
        print(f"Disconnected from MQTT broker with code: {rc}")
        
        # Try to reconnect to the next broker
        self._switch_broker()
        
    def _switch_broker(self) -> None:
        """Switch to the next available broker."""
        self.active_broker_index = (self.active_broker_index + 1) % len(MQTT_BROKERS)
        self.connect()
        
    def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            broker = MQTT_BROKERS[self.active_broker_index]
            client = self.clients[self.active_broker_index]
            
            client.connect(broker['host'], broker['port'])
            client.loop_start()
            return True
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            return False
            
    def disconnect(self) -> None:
        """Disconnect from all MQTT brokers."""
        for client in self.clients:
            client.loop_stop()
            client.disconnect()
            
    def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to a topic with a message handler."""
        self.message_handlers[topic] = handler
        for client in self.clients:
            client.subscribe(topic)
            
    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publish a message to a topic."""
        if not self.connected:
            print("Not connected to MQTT broker")
            return
            
        try:
            message = json.dumps(payload)
            # Publish to all connected brokers for redundancy
            for client in self.clients:
                if client.is_connected():
                    client.publish(topic, message)
        except Exception as e:
            print(f"Failed to publish message: {e}")
            
    def publish_block(self, block_data: Dict[str, Any]) -> None:
        """Publish a new block to the network."""
        self.publish(MQTT_TOPICS["BLOCKS"], block_data)
        
    def publish_transaction(self, transaction_data: Dict[str, Any]) -> None:
        """Publish a new transaction to the network."""
        self.publish(MQTT_TOPICS["TRANSACTIONS"], transaction_data)
        
    def publish_metrics(self, metrics_data: Dict[str, Any]) -> None:
        """Publish device metrics to the network."""
        self.publish(MQTT_TOPICS["METRICS"], metrics_data)
        
    def publish_validator_status(self, status_data: Dict[str, Any]) -> None:
        """Publish validator status to the network."""
        self.publish(MQTT_TOPICS["VALIDATOR_STATUS"], status_data)
        
    def get_network_status(self) -> Dict[str, Any]:
        """Get current network status."""
        return {
            "node_id": self.client_id,
            "connected": self.connected,
            "active_broker": MQTT_BROKERS[self.active_broker_index]["host"],
            "broker_count": len(MQTT_BROKERS),
            "message_handlers": len(self.message_handlers)
        } 