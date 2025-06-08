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
        self.storage = SQLiteStorage(db_path=f"blockchain_data/{self.node_id}_blockchain.db")
        self.metrics = BlockchainMetrics(self.node_id, self.storage)
        set_metrics_instance(self.metrics)
        self.dpos = DPoS(metrics=self.metrics)
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
        else:
            raise ValueError("Genesis block does not contain initial stake distribution.")

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
        print(f"[HANDLE BLOCK] Node {self.node_id} received new block: {block.hash} (Index: {block.index})")
        
        # Skip if we already have this block
        if any(b.hash == block.hash for b in self.blocks):
            print(f"[HANDLE BLOCK] Block {block.hash} already exists in chain.")
            return
            
        # Determine previous block's details for validation
        previous_block_timestamp = self.blocks[-1].timestamp if self.blocks else 0.0 # Use 0.0 or genesis block timestamp if no previous block
        previous_block_index = self.blocks[-1].index if self.blocks else -1 # Use -1 or genesis block index if no previous block

        if not self.blocks and block.index == 0: # This is the genesis block and we don't have it
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
                
    def _handle_incoming_metrics(self, metrics_data: dict) -> None:
        """Handle incoming metrics from any node and record them."""
        node_id = metrics_data.get('node_id')
        if node_id:
            self.metrics.record_node_metrics(node_id, metrics_data)
            print(f"[METRICS] Node {self.node_id} received metrics from {node_id}. Timestamp: {metrics_data.get('timestamp', 'N/A')}")
        
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
        
        # Get list of peer nodes (excluding self)
        peer_nodes = [
            node for node in RASPBERRY_PI_NODES 
            if node['id'] != self.node_id
        ]
        
        if not peer_nodes:
            print("No peer nodes found for synchronization.")
            return
            
        # Get local chain info
        local_chain_length = len(self.blocks)
        local_latest_hash = self.blocks[-1].hash if self.blocks else None
        
        print(f"Local chain length: {local_chain_length}, Latest hash: {local_latest_hash}")
        
        # Query each peer for their chain info
        for peer in peer_nodes:
            try:
                peer_url = f"http://{peer['ip']}:{peer['dashboard_port']}/api/chain_info"
                response = await self.http_client.get(peer_url)
                
                if response.status_code == 200:
                    peer_info = response.json()
                    peer_chain_length = peer_info['chain_length']
                    peer_latest_hash = peer_info['latest_block_hash']
                    
                    print(f"Peer {peer['id']} - Chain length: {peer_chain_length}, Latest hash: {peer_latest_hash}")
                    
                    # If peer has a longer chain or different latest hash, sync with it
                    if peer_chain_length > local_chain_length or (
                        peer_chain_length == local_chain_length and 
                        peer_latest_hash != local_latest_hash
                    ):
                        print(f"Chain divergence detected with peer {peer['id']}. Syncing...")
                        await self._sync_with_peer(peer, local_chain_length)
                        
            except Exception as e:
                print(f"Error querying peer {peer['id']}: {str(e)}")
                continue
                
    async def _sync_with_peer(self, peer: Dict[str, Any], local_chain_length: int) -> None:
        """Synchronize blocks with a specific peer."""
        try:
            # Request blocks from the peer
            peer_url = f"http://{peer['ip']}:{peer['dashboard_port']}/api/blocks"
            response = await self.http_client.get(
                peer_url,
                params={'start_index': local_chain_length, 'end_index': -1}  # -1 means get all remaining blocks
            )
            
            if response.status_code == 200:
                blocks_data = response.json()
                print(f"Received {len(blocks_data)} blocks from peer {peer['id']}")
                
                # Process received blocks
                for block_data in blocks_data:
                    block = Block.from_dict(block_data)
                    
                    # Determine previous block's details for validation during sync
                    # If current chain is empty, and syncing genesis, use 0.0 and -1
                    if not self.blocks:
                        previous_block_timestamp = 0.0
                        previous_block_index = -1
                    else:
                        # For subsequent blocks in the sync, previous is the last block in current chain
                        # or the block just processed from the received batch
                        previous_block_timestamp = self.blocks[-1].timestamp
                        previous_block_index = self.blocks[-1].index

                    # Verify block
                    if not self.dpos.validate_block(block, 0, previous_block_timestamp, previous_block_index):  # Power usage not critical for sync
                        print(f"Invalid block received from peer {peer['id']}")
                        continue
                        
                    # Check if block already exists
                    if any(b.hash == block.hash for b in self.blocks):
                        print(f"Block {block.hash} from peer {peer['id']} already exists.")
                        continue
                        
                    # Verify block chain
                    if block.previous_hash == self.blocks[-1].hash:
                        self.blocks.append(block)
                        self.storage.save_block(block)
                        print(f"Added block {block.index} from peer {peer['id']}")
                    else:
                        print(f"Block chain verification failed for block {block.index} from peer {peer['id']}. Previous hash mismatch: {block.previous_hash} != {self.blocks[-1].hash}")
                        
        except Exception as e:
            print(f"Error syncing with peer {peer['id']}: {str(e)}")
            
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
        
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Perform initial chain synchronization on startup
        print("Performing initial chain synchronization...")
        loop.run_until_complete(self._synchronize_chain())
        print("Initial chain synchronization complete.")

        try:
            while True:
                # Monitor system metrics
                metrics = self.energy_monitor.get_system_metrics()

                # Add system metrics as a pending transaction
                transaction = {
                    'type': 'system_metrics',
                    'timestamp': time.time(),
                    'data': metrics,
                    'node_id': self.node_id
                }
                self.pending_transactions.append(transaction)

                # Publish metrics
                self.mqtt_client.publish_metrics({
                    **metrics,
                    'node_id': self.node_id,
                    'block_count': len(self.blocks),
                    'pending_transactions': len(self.pending_transactions),
                    'current_stake': self.dpos.validators.get(self.node_id, 0),
                    'all_validators': self.dpos.validators,
                    'current_network_validator': self.dpos.get_current_validator(
                        reference_index=self.blocks[-1].index
                    ) if self.blocks else None,
                    'total_blocks': len(self.blocks),
                    'latest_block_hash': self.blocks[-1].hash if self.blocks else None
                })
                
                # Periodically update DPoS delegates based on liveness
                if time.time() % RASPBERRY_PI_SETTINGS['metrics_interval'] < 1: # Reuse metrics_interval for delegate updates
                    self.dpos._update_delegates()
                    print(f"[DPoS] Delegates updated. Active delegates: {self.dpos.delegates}")

                # Check system health
                if not self._check_system_health():
                    print("System needs throttling")
                    time.sleep(5)  # Add delay to reduce load
                    continue
                
                # Determine previous block's timestamp for timing checks
                last_block_timestamp = self.blocks[-1].timestamp if self.blocks else 0.0

                # Process pending transactions and create blocks if we're the current validator AND it's time to propose
                if self.dpos.is_time_to_propose_block(last_block_timestamp):
                    self._process_transactions()
                else:
                    print(f"[PROCESS TX] Not time to propose a block yet. Last block time: {last_block_timestamp}, Current time: {time.time()}")
                
                # Run chain synchronization periodically
                if time.time() % RASPBERRY_PI_SETTINGS['sync_interval'] < 1:
                    loop.run_until_complete(self._synchronize_chain())
                
                time.sleep(1)  # Prevent excessive CPU usage
                
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            self.mqtt_client.disconnect()
            loop.run_until_complete(self.http_client.aclose())
            loop.close()
        
    def _process_transactions(self) -> None:
        """Process pending transactions and create blocks if we're the current validator."""
        # Get previous block's timestamp and index for deterministic validator selection
        previous_block_timestamp = self.blocks[-1].timestamp if self.blocks else 0.0 # Use 0.0 for genesis block
        previous_block_index = self.blocks[-1].index if self.blocks else -1 # Use -1 for genesis block

        current_validator = self.dpos.get_current_validator(
            reference_index=previous_block_index
        )
        print(f"[PROCESS TX] Current DPoS validator: {current_validator}")
        print(f"[PROCESS TX] Node ID: {self.node_id}")

        if current_validator == self.node_id:
            print(f"[PROCESS TX] {self.node_id} is the current validator.")
            if self.pending_transactions:
                print(f"[PROCESS TX] {len(self.pending_transactions)} pending transactions found.")
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
                print(f"[PROCESS TX] No pending transactions on {self.node_id}.")
        else:
            print(f"[PROCESS TX] {self.node_id} is not the current validator.")

if __name__ == "__main__":
    node = BlockchainNode()
    node.start() 