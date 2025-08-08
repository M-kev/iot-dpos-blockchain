import os
import time
import json
import asyncio
import httpx
from typing import Dict, Any, List, Optional
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
from monitoring.dashboard import app as dashboard_app, set_metrics_instance
from storage.sqlite_storage import SQLiteStorage
from config.network_config import (
    get_node_config,
    RASPBERRY_PI_SETTINGS,
    NETWORK_SETTINGS,
    RASPBERRY_PI_NODES,
    MQTT_BROKERS,
    MQTT_TOPICS
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
        self.energy_monitor = EnergyMonitor()
        self.storage = SQLiteStorage(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'blockchain.db'))
        self.metrics = BlockchainMetrics(self.node_id, self.storage)
        set_metrics_instance(self.metrics)
        self.dpos = DPoS(metrics=self.metrics)
        print(f"[DEBUG] Initializing MQTT client for node: {self.node_id}")
        print(f"[DEBUG] Node config: {self.node_config}")
        print(f"[DEBUG] About to create MQTTClient instance...")
        self.mqtt_client = MQTTClient(self.node_id, self.node_config)
        print(f"[DEBUG] MQTTClient instance created successfully")
        
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
        
        # Initialize HTTP client for chain synchronization
        self.http_client = httpx.AsyncClient(timeout=NETWORK_SETTINGS['timeout'])
        
    def _initialize_blockchain(self) -> None:
        """Initialize blockchain with genesis block and stake distribution."""
        # Load blocks from storage
        stored_blocks = self.storage.get_blocks()
        
        if stored_blocks:
            self.blocks = stored_blocks
            print(f"Loaded {len(self.blocks)} blocks from database.")
        else:
            # If no blocks in storage, create and save genesis block
            genesis = GenesisBlock()
            genesis_block = genesis.create_genesis_block()
            
            # Verify genesis block (optional, but good practice)
            if not genesis.verify_genesis_block(genesis_block):
                raise ValueError("Invalid genesis block after creation")
                
            self.blocks.append(genesis_block)
            self.storage.save_block(genesis_block)
            print("Created and saved genesis block.")
        
        # Verify existing genesis block (loaded or newly created)
        genesis_verifier = GenesisBlock()
        if not genesis_verifier.verify_genesis_block(self.blocks[0]):
            raise ValueError("Invalid genesis block found in chain.")

        # Initialize validators with initial stakes from genesis block
        # This assumes initial stakes are in the first transaction of the genesis block
        initial_stakes_tx = next((tx for tx in self.blocks[0].transactions if tx.get('type') == 'stake_distribution'), None)
        if initial_stakes_tx and 'data' in initial_stakes_tx:
            initial_stakes = initial_stakes_tx['data']
            for node_id, stake in initial_stakes.items():
                self.dpos.add_validator(node_id, stake)
            print(f"Blockchain initialized with genesis block. Current stake for {self.node_id}: {self.dpos.validators.get(self.node_id, 0)}")
            print(f"[INIT] DPoS validators populated: {self.dpos.validators}")
        else:
            raise ValueError("Genesis block does not contain initial stake distribution.")

        # NEW: Initialize all_nodes_metrics with initial validators and current timestamp to mark as 'live'
        current_init_time = time.time()
        for node_id in self.dpos.validators.keys():
            self.metrics.all_nodes_metrics[node_id].update({
                'node_id': node_id,
                'timestamp': current_init_time, # Use current time for initial liveness
                'cpu_percent': 0,
                'memory_percent': 0,
                'temperature': 0,
                'power_usage': 0,
                'block_count': 0,
                'pending_transactions': 0,
                'current_stake': self.dpos.validators.get(node_id, 0),
                'is_validator': False,
            })
        print(f"[INIT] Initialized all_nodes_metrics with current time for validators' initial liveness: {current_init_time}")

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
        self.mqtt_client.subscribe(MQTT_TOPICS["BLOCKS"], self._handle_new_block)
        self.mqtt_client.subscribe(MQTT_TOPICS["TRANSACTIONS"], self._handle_new_transaction)
        self.mqtt_client.subscribe(MQTT_TOPICS["NETWORK_STATUS"], self._handle_network_status)
        self.mqtt_client.subscribe(MQTT_TOPICS["VALIDATOR_STATUS"], self._handle_validator_status)
        self.mqtt_client.subscribe(MQTT_TOPICS["METRICS"], self._handle_incoming_metrics)
        
    def _handle_new_block(self, block_data: dict) -> None:
        """Handle incoming new block."""
        block = Block.from_dict(block_data)
        print(f"[HANDLE BLOCK] Node {self.node_id} received new block: {block.hash} (Block Index: {block.block_index})")
        
        # Skip if we already have this block
        if any(b.hash == block.hash for b in self.blocks):
            print(f"[HANDLE BLOCK] Block {block.hash} already exists in chain.")
            return
            
        # Determine previous block's details for validation
        previous_block_timestamp = self.blocks[-1].timestamp if self.blocks else 0.0 # Use 0.0 or genesis block timestamp if no previous block
        previous_block_index = self.blocks[-1].block_index if self.blocks else -1 # Use -1 or genesis block index if no previous block

        if not self.blocks and block.block_index == 0: # This is the genesis block and we don't have it
            previous_block_timestamp = 0.0 # No actual previous block for genesis
            previous_block_index = -1 # No actual previous block for genesis

        # Check energy metrics before validation
        energy_metrics = self.energy_monitor.get_system_metrics()
        if self.dpos.validate_block(block, energy_metrics['power_usage'], previous_block_timestamp, previous_block_index):
            print(f"[HANDLE BLOCK] Block {block.hash} validation successful.")
            # Verify block chain (check previous hash)
            if self.blocks and block.previous_hash == self.blocks[-1].hash:
                self.blocks.append(block)
                self.storage.save_block(block)
                
                # Record metrics
                self.metrics.record_block_time(time.time() - block.timestamp)
                self.metrics.record_consensus_time(
                    block.energy_metrics.get('consensus_time', 0)
                )
                
                print(f"[HANDLE BLOCK] New block {block.hash} added to chain.")
            else:
                print(f"[HANDLE BLOCK] Block chain verification failed for block {block.hash}. Previous hash mismatch or empty chain. Incoming previous_hash: {block.previous_hash}, Local last block hash: {self.blocks[-1].hash if self.blocks else 'N/A'}")
        else:
            print(f"[HANDLE BLOCK] Block {block.hash} validation failed.")
        
    def _handle_new_transaction(self, transaction_data: Dict[str, Any]) -> None:
        """Handle incoming new transaction."""
        self.pending_transactions.append(transaction_data)
        # Record one new transaction event for TPS
        self.metrics.record_transactions(1)
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
                
    def _handle_incoming_metrics(self, metrics_data: dict) -> None:
        """Handle incoming metrics from any node and record them."""
        node_id = metrics_data.get('node_id')
        if node_id:
            self.metrics.record_node_metrics(node_id, metrics_data)
            print(f"[METRICS] Node {self.node_id} received metrics from {node_id}. Timestamp: {metrics_data.get('timestamp', 'N/A')}")
            # Add metrics as a transaction
            self.pending_transactions.append({
                "type": "metrics",
                "node_id": node_id,
                "metrics": metrics_data,
                "timestamp": metrics_data.get("timestamp", time.time())
            })
            # Record one new transaction event for TPS
            self.metrics.record_transactions(1)
            self.dpos._update_delegates()
        
    def _check_system_health(self) -> bool:
        """Check if the system is healthy enough to process blocks."""
        metrics = self.energy_monitor.get_system_metrics()
        
        # Check temperature
        if metrics['temperature'] > RASPBERRY_PI_SETTINGS['cpu_throttle_temp']:
            print(f"[HEALTH CHECK] System temperature too high: {metrics['temperature']}°C")
            return False
            
        # Check CPU usage
        if metrics['cpu_percent'] > RASPBERRY_PI_SETTINGS['max_cpu_usage']:
            print(f"[HEALTH CHECK] CPU usage too high: {metrics['cpu_percent']:.2f}%")
            return False
            
        # Check memory usage
        if metrics['memory_percent'] > RASPBERRY_PI_SETTINGS['max_memory_usage']:
            print(f"[HEALTH CHECK] Memory usage too high: {metrics['memory_percent']:.2f}%")
            return False
            
        print(f"[HEALTH CHECK] System is healthy. CPU: {metrics['cpu_percent']:.2f}%, Mem: {metrics['memory_percent']:.2f}%, Temp: {metrics['temperature']}°C")
        return True
        
    async def _synchronize_chain(self) -> None:
        """Synchronize the local blockchain with peer nodes."""
        print("Starting chain synchronization...")
        local_chain_length = len(self.blocks)
        print(f"Local chain length: {local_chain_length}, Latest hash: {self.blocks[-1].hash if self.blocks else 'None'}")
        
        # Get peer nodes from configuration
        peers = [node for node in RASPBERRY_PI_NODES if node['id'] != self.node_id]
        print(f"Found {len(peers)} peer nodes to sync with")
        
        for peer in peers:
            try:
                print(f"Attempting to sync with peer: {peer['id']} at {peer['ip']}:{peer['dashboard_port']}")
                await self._sync_with_peer(peer, local_chain_length)
            except Exception as e:
                print(f"Error querying peer {peer['id']}: {e}")
        
        print("Chain synchronization complete")
        # Update delegates after synchronization
        self.dpos._update_delegates()
        print("Delegates updated after chain synchronization.")
        
    async def _sync_with_peer(self, peer: Dict[str, Any], local_chain_length: int) -> None:
        """Synchronize with a specific peer node."""
        try:
            peer_url = f"http://{peer['ip']}:{peer['dashboard_port']}/api/blocks"
            params = {'start_index': local_chain_length, 'end_index': -1}
            
            print(f"[SYNC] Requesting blocks from {peer['id']} at {peer_url}")
            response = await self.http_client.get(peer_url, params=params)
            
            if response.status_code == 200:
                blocks_data = response.json()
                print(f"[SYNC] Received {len(blocks_data)} blocks from {peer['id']}")
                
                if blocks_data:
                    # Get current chain state for validation
                    current_prev_block_index = self.blocks[-1].block_index if self.blocks else -1
                    current_prev_block_timestamp = self.blocks[-1].timestamp if self.blocks else 0.0
                    
                    print(f"[SYNC] Node {self.node_id} starting to process {len(blocks_data)} blocks from {peer['id']}. Initial previous block: Index={current_prev_block_index}, Timestamp={current_prev_block_timestamp}")
                    
                    for block_data in blocks_data:
                        try:
                            block = Block.from_dict(block_data)
                            print(f"[SYNC] Processing block {block.block_index} ({block.hash}) from peer {peer['id']}")
                            
                            # During sync, be more lenient with validator checking
                            # Only check basic block structure, not strict validator validation
                            if (block.block_index > current_prev_block_index and 
                                block.timestamp > current_prev_block_timestamp and
                                block.previous_hash == (self.blocks[-1].hash if self.blocks else "0" * 64)):
                                
                                # Add block to local chain
                                self.blocks.append(block)
                                self.storage.save_block(block)
                                print(f"[SYNC] Added block {block.block_index} from {peer['id']} to local chain")
                                
                                # Update chain state for next iteration
                                current_prev_block_index = block.block_index
                                current_prev_block_timestamp = block.timestamp
                            else:
                                print(f"[SYNC] Skipping block {block.block_index} from {peer['id']} - validation failed")
                                
                        except Exception as e:
                            print(f"[SYNC] Error processing block from {peer['id']}: {e}")
                            continue
                    
                    print(f"[SYNC] Sync with {peer['id']} complete. Local chain length: {len(self.blocks)}")
                else:
                    print(f"[SYNC] No new blocks from {peer['id']}")
            else:
                print(f"[SYNC] Failed to get blocks from {peer['id']}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"[SYNC] Error syncing with {peer['id']}: {e}")
            
    async def start(self) -> None:
        """Start the blockchain node operations."""
        print(f"Blockchain node {self.node_id} started")
        print(f"Current stake: {self.dpos.validators.get(self.node_id, 0)}")
        
        # Start dashboard in a separate thread
        self.dashboard_thread.start()
        
        # Connect to MQTT broker
        print(f"[DEBUG] Attempting to connect to MQTT brokers...")
        print(f"[DEBUG] MQTT client object: {self.mqtt_client}")
        print(f"[DEBUG] MQTT client type: {type(self.mqtt_client)}")
        connection_result = self.mqtt_client.connect()
        print(f"[DEBUG] Connection result: {connection_result}")
        if not connection_result:
            print(f"[ERROR] Failed to connect to MQTT broker for node {self.node_id}")
        else:
            print(f"[DEBUG] Successfully connected to MQTT broker for node {self.node_id}")
            # Show which broker we're connected to
            network_status = self.mqtt_client.get_network_status()
            print(f"[DEBUG] Connected to broker: {network_status['active_broker']}")
        
        # Perform initial chain synchronization
        print("Performing initial chain synchronization...")
        await self._synchronize_chain()

        # Update delegates for the first time after sync, 
        # ensuring self.metrics.all_nodes_metrics has initial values
        self.dpos._update_delegates(force_update=True)

        # Start periodic tasks
        self.periodic_tasks = [
            asyncio.create_task(self._publish_metrics_periodically()),
            asyncio.create_task(self._process_transactions_periodically()),
            asyncio.create_task(self._synchronize_chain_periodically())
        ]
        await asyncio.gather(*self.periodic_tasks)

    # Publish system metrics
    async def _publish_metrics_periodically(self):
        """Publish system metrics periodically."""
        while True:
            try:
                # Get system metrics
                system_metrics = self.energy_monitor.get_system_metrics()
                
                # Prepare metrics data
                metrics_to_publish = {
                    'node_id': self.node_id,
                    'timestamp': time.time(),
                    'cpu_percent': system_metrics['cpu_percent'],
                    'memory_percent': system_metrics['memory_percent'],
                    'temperature': system_metrics['temperature'],
                    'power_usage': system_metrics['power_usage'],
                    'block_count': len(self.blocks),
                    'pending_transactions': len(self.pending_transactions),
                    'current_stake': self.dpos.validators.get(self.node_id, 0),
                    'all_validators': self.dpos.validators,
                    'current_network_validator': self.dpos.get_current_validator(
                        reference_block_index=self.blocks[-1].block_index if self.blocks else -1
                    ),
                }
                
                # Add debug logging for validator selection
                current_block_index = self.blocks[-1].block_index if self.blocks else -1
                print(f"[DEBUG] Node {self.node_id} using block_index {current_block_index} for validator selection")
                print(f"[DEBUG] Node {self.node_id} chain length: {len(self.blocks)}")
                
                # Record local metrics
                local_metrics_for_record = metrics_to_publish.copy()
                self.metrics.record_node_metrics(self.node_id, local_metrics_for_record)
                
                print(f"[DEBUG] About to publish metrics. MQTT client connected: {self.mqtt_client.connected}")
                print(f"[DEBUG] MQTT client object: {self.mqtt_client}")
                
                # Publish metrics
                self.mqtt_client.publish_metrics(metrics_to_publish)
                print(f"[METRICS] Node {self.node_id} published metrics. Timestamp: {metrics_to_publish['timestamp']}")
                
            except Exception as e:
                print(f"[ERROR] Failed to publish metrics: {e}")
                
            await asyncio.sleep(RASPBERRY_PI_SETTINGS['metrics_interval'])

    # Process pending transactions and create blocks if we're the current validator
    async def _process_transactions_periodically(self):
        while True:
            # Get previous block's timestamp and index for deterministic validator selection
            previous_block_timestamp = self.blocks[-1].timestamp if self.blocks else 0.0 # Use 0.0 for genesis block
            previous_block_index = self.blocks[-1].block_index if self.blocks else -1 # Use -1 for genesis block

            current_validator = self.dpos.get_current_validator(
                reference_block_index=self.blocks[-1].block_index if self.blocks else -1
            )
            print(f"[PROCESS TX] Current DPoS validator: {current_validator}")
            print(f"[PROCESS TX] Node ID: {self.node_id}")

            # Normalize current_validator and self.node_id for comparison
            print(f"[PROCESS TX DEBUG] Node ID: {self.node_id.strip().lower()}")
            print(f"[PROCESS TX DEBUG] Current Validator: {current_validator.strip().lower()}")
            if current_validator.strip().lower() == self.node_id.strip().lower():
                print(f"[PROCESS TX] {self.node_id} is the current validator.")
                # Proceed with block proposal
            else:
                print(f"[PROCESS TX] {self.node_id} is not the current validator.")
                await asyncio.sleep(1) # Check frequently
                continue

            # Check system health before proposing a block
            if not self._check_system_health():
                print(f"[PROCESS TX] System not healthy for {self.node_id}. Skipping block proposal.")
                await asyncio.sleep(1) # Short delay before re-checking
                continue
            else:
                print(f"[PROCESS TX] System health check passed for {self.node_id}.")

            # Check if enough time has passed since the last block
            if not self.dpos.is_time_to_propose_block(previous_block_timestamp):
                print(f"[PROCESS TX] Not time to propose a block yet. Last block time: {previous_block_timestamp}, Current time: {time.time()}")
                await asyncio.sleep(1) # Wait a bit before next attempt
                continue
            else:
                print(f"[PROCESS TX] Time to propose a block for {self.node_id}.")

            if self.pending_transactions:
                print(f"[PROCESS TX] {len(self.pending_transactions)} pending transactions found.")
                start_time = time.time()

                # Create new block
                new_block = Block(
                    block_index=len(self.blocks),
                    timestamp=time.time(),
                    transactions=self.pending_transactions[:10],  # Limit transactions per block
                    previous_hash=self.blocks[-1].hash if self.blocks else "0" * 64,
                    validator=current_validator,
                    energy_metrics={
                        **self.energy_monitor.get_system_metrics(),
                        'consensus_time': time.time() - start_time
                    }
                )

                print(f"[PROCESS TX] New block created with index {new_block.block_index} and hash {new_block.hash}.")

                # Record propagation delay
                self.metrics.record_propagation_delay(time.time() - start_time)

                # Publish new block
                self.mqtt_client.publish_block(new_block.to_dict())
                print(f"[PROCESS TX] Node {self.node_id} published new block: {new_block.hash}")

                # Add block to local chain and save to storage
                self.blocks.append(new_block)
                self.storage.save_block(new_block)
                print(f"[PROCESS TX] Block {new_block.hash} added to local chain and saved.")

                # Publish validator status
                self.mqtt_client.publish_validator_status({
                    'node_id': self.node_id,
                    'block_count': len(self.blocks),
                    'stake': self.dpos.validators.get(self.node_id, 0),
                    'is_validator': True
                })

                # Clear processed transactions
                self.pending_transactions = self.pending_transactions[10:]
            else:
                print("[PROCESS TX] No pending transactions to process.")
            await asyncio.sleep(1) # Check frequently

    async def _synchronize_chain_periodically(self):
        """Periodically synchronize the local blockchain with peer nodes."""
        while True:
            await self._synchronize_chain()
            await asyncio.sleep(RASPBERRY_PI_SETTINGS['sync_interval'])

if __name__ == "__main__":
    node = BlockchainNode()
    asyncio.run(node.start())  # Use asyncio.run to execute the coroutine