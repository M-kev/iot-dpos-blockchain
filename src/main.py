import os
import time
import json
from typing import Dict, Any
from dotenv import load_dotenv
import uvicorn
import threading
import socket

from consensus.block import Block
from consensus.dpos import DPoS
from consensus.genesis import GenesisBlock
from network.mqtt_client import MQTTClient
from energy.monitor import EnergyMonitor
from monitoring.metrics import BlockchainMetrics
from monitoring.dashboard import app as dashboard_app
from config.network_config import (
    get_node_config,
    RASPBERRY_PI_SETTINGS,
    NETWORK_SETTINGS
)

class BlockchainNode:
    def __init__(self):
        load_dotenv()
        
        # Get node configuration
        self.node_id = os.getenv('NODE_ID', 'pi_node_1')
        self.node_config = get_node_config(self.node_id)
        
        if not self.node_config:
            raise ValueError(f"Invalid node ID: {self.node_id}")
        
        # Initialize components
        self.dpos = DPoS()
        self.energy_monitor = EnergyMonitor()
        self.metrics = BlockchainMetrics()
        self.mqtt_client = MQTTClient(self.node_id, self.node_config)
        
        # Initialize blockchain with genesis block
        self.blocks = []
        self._initialize_blockchain()
        
        # Setup message handlers
        self._setup_handlers()
        
        # Initialize transaction pool
        self.pending_transactions = []
        
        # Start dashboard in a separate thread
        self.dashboard_thread = threading.Thread(
            target=self._start_dashboard,
            daemon=True
        )
        
    def _initialize_blockchain(self) -> None:
        """Initialize blockchain with genesis block and stake distribution."""
        # Load or create genesis block
        genesis = GenesisBlock()
        genesis_block = genesis.load_genesis_block()
        
        # Verify genesis block
        if not genesis.verify_genesis_block(genesis_block):
            raise ValueError("Invalid genesis block")
            
        # Add genesis block to chain
        self.blocks.append(genesis_block)
        
        # Initialize validators with initial stakes
        initial_stakes = genesis.get_initial_stakes()
        for node_id, stake in initial_stakes.items():
            self.dpos.add_validator(node_id, stake)
            
        print(f"Blockchain initialized with genesis block. Initial stake: {initial_stakes[self.node_id]}")
        
    def _start_dashboard(self):
        """Start the dashboard server."""
        uvicorn.run(
            dashboard_app,
            host="0.0.0.0",
            port=self.node_config['dashboard_port'],
            log_level="info"
        )
        
    def _setup_handlers(self) -> None:
        """Setup MQTT message handlers."""
        self.mqtt_client.subscribe('blocks/new', self._handle_new_block)
        self.mqtt_client.subscribe('transactions/new', self._handle_new_transaction)
        self.mqtt_client.subscribe('network/status', self._handle_network_status)
        self.mqtt_client.subscribe('validator/status', self._handle_validator_status)
        
    def _handle_new_block(self, block_data: Dict[str, Any]) -> None:
        """Handle incoming new block."""
        block = Block.from_dict(block_data)
        
        # Skip if we already have this block
        if any(b.hash == block.hash for b in self.blocks):
            return
            
        # Check energy metrics before validation
        energy_metrics = self.energy_monitor.get_system_metrics()
        if self.dpos.validate_block(block, energy_metrics['power_usage']):
            # Verify block chain
            if block.previous_hash == self.blocks[-1].hash:
                self.blocks.append(block)
                
                # Record metrics
                self.metrics.record_block_time(time.time() - block.timestamp)
                self.metrics.record_consensus_time(
                    block.energy_metrics.get('consensus_time', 0)
                )
                
                print(f"New block added: {block.hash}")
                
    def _handle_new_transaction(self, transaction_data: Dict[str, Any]) -> None:
        """Handle incoming new transaction."""
        self.pending_transactions.append(transaction_data)
        self.metrics.record_transactions(len(self.pending_transactions))
        print(f"New transaction received: {transaction_data}")
        
    def _handle_network_status(self, status_data: Dict[str, Any]) -> None:
        """Handle network status updates."""
        # Adjust block time based on network load
        self.dpos.adjust_block_time(status_data.get('network_load', 0.5))
        
    def _handle_validator_status(self, status_data: Dict[str, Any]) -> None:
        """Handle validator status updates."""
        # Update validator list and stakes
        if 'validators' in status_data:
            for validator in status_data['validators']:
                self.dpos.add_validator(
                    validator['address'],
                    validator['stake']
                )
                
    def _check_system_health(self) -> bool:
        """Check if the system is healthy enough to process blocks."""
        metrics = self.energy_monitor.get_system_metrics()
        
        # Check temperature
        if metrics['temperature'] > RASPBERRY_PI_SETTINGS['cpu_throttle_temp']:
            print("System temperature too high")
            return False
            
        # Check CPU usage
        if metrics['cpu_percent'] > RASPBERRY_PI_SETTINGS['max_cpu_usage']:
            print("CPU usage too high")
            return False
            
        # Check memory usage
        if metrics['memory_percent'] > RASPBERRY_PI_SETTINGS['max_memory_usage']:
            print("Memory usage too high")
            return False
            
        return True
        
    def start(self) -> None:
        """Start the blockchain node."""
        # Start dashboard
        self.dashboard_thread.start()
        
        # Connect to MQTT broker
        if not self.mqtt_client.connect():
            print("Failed to connect to MQTT broker")
            return
            
        print(f"Blockchain node {self.node_id} started")
        print(f"Current stake: {self.dpos.validators.get(self.node_id, 0)}")
        
        try:
            while True:
                # Monitor system metrics
                metrics = self.energy_monitor.get_system_metrics()
                
                # Publish metrics
                self.mqtt_client.publish_metrics({
                    **metrics,
                    'node_id': self.node_id,
                    'block_count': len(self.blocks),
                    'pending_transactions': len(self.pending_transactions),
                    'current_stake': self.dpos.validators.get(self.node_id, 0)
                })
                
                # Check system health
                if not self._check_system_health():
                    print("System needs throttling")
                    time.sleep(5)  # Add delay to reduce load
                    continue
                    
                # Process pending transactions and create blocks if we're the current validator
                self._process_transactions()
                
                time.sleep(1)  # Prevent excessive CPU usage
                
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            self.mqtt_client.disconnect()
            
    def _process_transactions(self) -> None:
        """Process pending transactions and create blocks if we're the current validator."""
        current_validator = self.dpos.get_current_validator()
        
        if current_validator == self.node_id:
            if self.pending_transactions:
                start_time = time.time()
                
                # Create new block
                new_block = Block(
                    index=len(self.blocks),
                    timestamp=time.time(),
                    transactions=self.pending_transactions[:10],  # Limit transactions per block
                    previous_hash=self.blocks[-1].hash if self.blocks else "0" * 64,
                    validator=current_validator,
                    energy_metrics={
                        **self.energy_monitor.get_system_metrics(),
                        'consensus_time': time.time() - start_time
                    }
                )
                
                # Record propagation delay
                self.metrics.record_propagation_delay(time.time() - start_time)
                
                # Publish new block
                self.mqtt_client.publish_block(new_block.to_dict())
                
                # Publish validator status
                self.mqtt_client.publish_validator_status({
                    'node_id': self.node_id,
                    'block_count': len(self.blocks),
                    'stake': self.dpos.validators.get(self.node_id, 0),
                    'is_validator': True
                })
                
                # Clear processed transactions
                self.pending_transactions = self.pending_transactions[10:]

if __name__ == "__main__":
    node = BlockchainNode()
    node.start() 