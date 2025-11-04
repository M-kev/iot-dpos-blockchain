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
import hashlib

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
        print(f"[METRICS] Resource monitoring initialized for node {self.node_id}")
        print(f"[METRICS] Monitoring: block_validation, block_creation, network_operations, database_operations")
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
        # Always create a canonical genesis block to ensure consistency
        genesis = GenesisBlock()
        canonical_genesis = genesis.create_genesis_block()
        canonical_genesis_hash = canonical_genesis.hash
        
        # Load blocks from storage
        stored_blocks = self.storage.get_blocks()
        
        if stored_blocks and len(stored_blocks) > 0:
            # Check if the stored genesis block matches the canonical one
            stored_genesis = stored_blocks[0]
            genesis_verifier = GenesisBlock()
            
            if stored_genesis.block_index == 0:
                # Verify the stored genesis block matches canonical
                stored_genesis_hash = stored_genesis.hash
                
                # Recalculate hash to ensure it matches (in case of serialization issues)
                if stored_genesis_hash != canonical_genesis_hash:
                    print(f"[INIT] WARNING: Stored genesis block hash ({stored_genesis_hash[:16]}...) doesn't match canonical ({canonical_genesis_hash[:16]}...). Replacing with canonical genesis.")
                    # Replace the genesis block with canonical one
                    self.blocks = [canonical_genesis]
                    self.storage.save_block(canonical_genesis)
                    # Keep the rest of the blocks if any
                    if len(stored_blocks) > 1:
                        # Check if subsequent blocks are valid
                        for block in stored_blocks[1:]:
                            if block.previous_hash == canonical_genesis.hash or (len(self.blocks) > 0 and block.previous_hash == self.blocks[-1].hash):
                                self.blocks.append(block)
                            else:
                                print(f"[INIT] Discarding block {block.block_index} - chain broken after genesis replacement")
                    print(f"[INIT] Replaced genesis block. Chain now has {len(self.blocks)} blocks.")
                elif not genesis_verifier.verify_genesis_block(stored_genesis):
                    print(f"[INIT] WARNING: Stored genesis block doesn't pass verification. Replacing with canonical genesis.")
                    self.blocks = [canonical_genesis]
                    self.storage.save_block(canonical_genesis)
                    if len(stored_blocks) > 1:
                        for block in stored_blocks[1:]:
                            if block.previous_hash == canonical_genesis.hash or (len(self.blocks) > 0 and block.previous_hash == self.blocks[-1].hash):
                                self.blocks.append(block)
                            else:
                                print(f"[INIT] Discarding block {block.block_index} - chain broken after genesis replacement")
                    print(f"[INIT] Replaced genesis block. Chain now has {len(self.blocks)} blocks.")
                else:
                    # Genesis matches, use stored blocks
                    self.blocks = stored_blocks
                    print(f"Loaded {len(self.blocks)} blocks from database.")
            else:
                # No genesis block in storage, add canonical one
                print(f"[INIT] WARNING: No genesis block found in storage. Adding canonical genesis.")
                self.blocks = [canonical_genesis] + stored_blocks
                self.storage.save_block(canonical_genesis)
        else:
            # No blocks in storage, create and save canonical genesis block
            self.blocks = [canonical_genesis]
            self.storage.save_block(canonical_genesis)
            print("Created and saved canonical genesis block.")
        
        # Final verification
        genesis_verifier = GenesisBlock()
        if not genesis_verifier.verify_genesis_block(self.blocks[0]):
            raise ValueError("Invalid genesis block found in chain after initialization.")
        
        # Verify genesis hash matches canonical
        if self.blocks[0].hash != canonical_genesis_hash:
            print(f"[INIT] CRITICAL: Genesis hash mismatch. Replacing with canonical.")
            self.blocks[0] = canonical_genesis
            self.storage.save_block(canonical_genesis)

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

        # Initialize all_nodes_metrics structure but DON'T mark nodes as live until they send metrics
        # This ensures offline detection works correctly from the start
        for node_id in self.dpos.validators.keys():
            self.metrics.all_nodes_metrics[node_id].update({
                'node_id': node_id,
                'timestamp': 0,  # 0 means no metrics received yet - won't be considered live
                'cpu_percent': 0,
                'memory_percent': 0,
                'temperature': 0,
                'power_usage': 0,
                'block_count': 0,
                'pending_transactions': 0,
                'current_stake': self.dpos.validators.get(node_id, 0),
                'is_validator': False,
            })
        print(f"[INIT] Initialized all_nodes_metrics structure for validators (nodes will be marked live when they send metrics)")

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
        
        # Monitor resource usage during block validation
        # Note: This only monitors blocks received via MQTT, not blocks synced via HTTP
        # Historical blocks (created before this feature was deployed) won't have metrics
        with self.metrics.monitor_operation('block_validation', f"validate_block_{block.block_index}"):
            validation_result = self.dpos.validate_block(block, energy_metrics['power_usage'], previous_block_timestamp, previous_block_index)
        
        if validation_result:
            print(f"[HANDLE BLOCK] Block {block.hash} validation successful.")
            # Verify block chain (check previous hash)
            if self.blocks and block.previous_hash == self.blocks[-1].hash:
                self.blocks.append(block)
                
                # Monitor database operation during block save
                start_time = time.time()
                self.storage.save_block(block)
                self.metrics.record_database_operation('save_block', time.time() - start_time, 1)
                
                # Record metrics
                self.metrics.record_block_time(block.timestamp - previous_block_timestamp)
                self.metrics.record_consensus_time(
                    block.energy_metrics.get('consensus_time', 0)
                )
                
                # Persist per-block analytics
                try:
                    # For genesis block (index 0), interval should be 0
                    interval = 0 if block.block_index == 0 else block.timestamp - previous_block_timestamp
                    consensus_time = block.energy_metrics.get('consensus_time', 0)
                    power_usage = block.energy_metrics.get('power_usage', 0)
                    
                    # Monitor database operation for block metrics
                    start_time = time.time()
                    self.storage.save_block_metrics(block.block_index, block.timestamp, interval, consensus_time, power_usage)
                    self.metrics.record_database_operation('save_block_metrics', time.time() - start_time, 1)
                except Exception as e:
                    print(f"[ANALYTICS] Failed saving block metrics for received block {block.block_index}: {e}")
                
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
        
        # Record transaction received time for lifecycle
        try:
            tx_string = json.dumps(transaction_data, sort_keys=True)
            tx_hash = hashlib.sha256(tx_string.encode()).hexdigest()
            self.storage.record_tx_received(tx_hash, time.time())
        except Exception as e:
            print(f"[LIFECYCLE] Failed to record tx received: {e}")
        
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
            tx = {
                "type": "metrics",
                "node_id": node_id,
                "metrics": metrics_data,
                "timestamp": metrics_data.get("timestamp", time.time())
            }
            self.pending_transactions.append(tx)
            # Record one new transaction event for TPS
            self.metrics.record_transactions(1)
            # Record transaction received lifecycle for metrics-derived transactions
            try:
                tx_string = json.dumps(tx, sort_keys=True)
                tx_hash = hashlib.sha256(tx_string.encode()).hexdigest()
                self.storage.record_tx_received(tx_hash, time.time())
            except Exception as e:
                print(f"[LIFECYCLE] Failed to record metrics tx received: {e}")
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
            
            # Monitor network operation during HTTP sync
            sync_start = time.time()
            response = await self.http_client.get(peer_url, params=params)
            sync_duration = time.time() - sync_start
            
            # Estimate data size (rough approximation)
            response_size = len(str(response.content)) if hasattr(response, 'content') else 0
            self.metrics.record_network_operation('http_sync', response_size, sync_duration, response.status_code == 200)
            
            if response.status_code == 200:
                blocks_data = response.json()
                print(f"[SYNC] Received {len(blocks_data)} blocks from {peer['id']}")
                
                if blocks_data:
                    # Get the full chain from peer to find common ancestor
                    # Request all blocks to find where chains diverge
                    full_chain_params = {'start_index': 0, 'end_index': -1}
                    full_chain_response = await self.http_client.get(peer_url, params=full_chain_params)
                    
                    if full_chain_response.status_code == 200:
                        peer_blocks_data = full_chain_response.json()
                        print(f"[SYNC] Got full chain from {peer['id']}: {len(peer_blocks_data)} blocks")
                        
                        # Find common ancestor (blocks that match by index and hash)
                        # Start from genesis (index 0) which should always match
                        common_ancestor_index = -1
                        min_length = min(len(self.blocks), len(peer_blocks_data))
                        
                        for i in range(min_length):
                            peer_block = Block.from_dict(peer_blocks_data[i])
                            local_block = self.blocks[i]
                            
                            # Check if blocks match by both index and hash
                            if (local_block.block_index == peer_block.block_index and 
                                local_block.hash == peer_block.hash):
                                common_ancestor_index = i
                            else:
                                # Chains have diverged, stop here
                                break
                        
                        # If no common ancestor found (shouldn't happen, but handle it)
                        if common_ancestor_index == -1 and len(self.blocks) > 0 and len(peer_blocks_data) > 0:
                            # Check if genesis blocks match
                            local_genesis = self.blocks[0]
                            peer_genesis = Block.from_dict(peer_blocks_data[0])
                            print(f"[SYNC] DEBUG: Local genesis index={local_genesis.block_index}, hash={local_genesis.hash[:16]}...")
                            print(f"[SYNC] DEBUG: Peer genesis index={peer_genesis.block_index}, hash={peer_genesis.hash[:16]}...")
                            if (local_genesis.block_index == peer_genesis.block_index and 
                                local_genesis.hash == peer_genesis.hash):
                                common_ancestor_index = 0
                                print(f"[SYNC] Genesis blocks match, setting common ancestor to 0")
                            else:
                                print(f"[SYNC] WARNING: Genesis blocks don't match! This should never happen.")
                        
                        print(f"[SYNC] Common ancestor with {peer['id']} at block index {common_ancestor_index} (local chain: {len(self.blocks)}, peer chain: {len(peer_blocks_data)})")
                        
                        # If peer has longer chain, replace our chain from common ancestor onwards
                        if len(peer_blocks_data) > len(self.blocks) and common_ancestor_index >= 0:
                            print(f"[SYNC] Peer {peer['id']} has longer chain ({len(peer_blocks_data)} vs {len(self.blocks)}). Adopting peer's chain from block {common_ancestor_index + 1}")
                            
                            # Remove blocks after common ancestor from local chain
                            blocks_removed = len(self.blocks) - (common_ancestor_index + 1)
                            if blocks_removed > 0:
                                print(f"[SYNC] Removing {blocks_removed} divergent blocks from local chain")
                            self.blocks = self.blocks[:common_ancestor_index + 1]
                            
                            # Add peer's blocks from after common ancestor
                            for peer_block_data in peer_blocks_data[common_ancestor_index + 1:]:
                                try:
                                    block = Block.from_dict(peer_block_data)
                                    
                                    # Verify block extends our chain correctly
                                    if self.blocks and block.previous_hash != self.blocks[-1].hash:
                                        print(f"[SYNC] Warning: Block {block.block_index} previous_hash doesn't match our chain tip. Skipping.")
                                        continue
                                    
                                    self.blocks.append(block)
                                    self.storage.save_block(block)
                                    # Persist per-block analytics
                                    try:
                                        prev_timestamp = self.blocks[-2].timestamp if len(self.blocks) > 1 else 0.0
                                        interval = 0 if block.block_index == 0 else block.timestamp - prev_timestamp
                                        consensus_time = block.energy_metrics.get('consensus_time', 0)
                                        power_usage = block.energy_metrics.get('power_usage', 0)
                                        self.storage.save_block_metrics(block.block_index, block.timestamp, interval, consensus_time, power_usage)
                                    except Exception as e:
                                        print(f"[ANALYTICS] Failed saving block metrics during sync: {e}")
                                    print(f"[SYNC] Adopted block {block.block_index} from {peer['id']}")
                                except Exception as e:
                                    print(f"[SYNC] Error processing block from {peer['id']}: {e}")
                                    continue
                        elif len(peer_blocks_data) > len(self.blocks) and common_ancestor_index == -1:
                            # Chains have completely diverged, but peer is longer - adopt if genesis matches
                            if len(self.blocks) > 0 and len(peer_blocks_data) > 0:
                                local_genesis = self.blocks[0]
                                peer_genesis = Block.from_dict(peer_blocks_data[0])
                                if local_genesis.hash == peer_genesis.hash:
                                    print(f"[SYNC] Chains diverged but genesis matches. Adopting peer's longer chain.")
                                    # Replace entire chain with peer's (except genesis which matches)
                                    self.blocks = [local_genesis]  # Keep our genesis
                                    # Add all peer blocks after genesis
                                    for peer_block_data in peer_blocks_data[1:]:
                                        block = Block.from_dict(peer_block_data)
                                        self.blocks.append(block)
                                        self.storage.save_block(block)
                                        try:
                                            prev_timestamp = self.blocks[-2].timestamp
                                            interval = block.timestamp - prev_timestamp
                                            consensus_time = block.energy_metrics.get('consensus_time', 0)
                                            power_usage = block.energy_metrics.get('power_usage', 0)
                                            self.storage.save_block_metrics(block.block_index, block.timestamp, interval, consensus_time, power_usage)
                                        except Exception as e:
                                            print(f"[ANALYTICS] Failed saving block metrics: {e}")
                                        print(f"[SYNC] Adopted block {block.block_index} from {peer['id']}")
                        elif common_ancestor_index >= 0:
                            # Same length or shorter, but check if we missed any blocks
                            for peer_block_data in peer_blocks_data[common_ancestor_index + 1:]:
                                peer_block = Block.from_dict(peer_block_data)
                                if peer_block.block_index > (self.blocks[-1].block_index if self.blocks else -1):
                                    # This block is ahead of us, add it
                                    if self.blocks and peer_block.previous_hash != self.blocks[-1].hash:
                                        print(f"[SYNC] Block {peer_block.block_index} doesn't extend our chain. Skipping.")
                                        continue
                                    self.blocks.append(peer_block)
                                    self.storage.save_block(peer_block)
                                    try:
                                        prev_timestamp = self.blocks[-2].timestamp if len(self.blocks) > 1 else 0.0
                                        interval = 0 if peer_block.block_index == 0 else peer_block.timestamp - prev_timestamp
                                        consensus_time = peer_block.energy_metrics.get('consensus_time', 0)
                                        power_usage = peer_block.energy_metrics.get('power_usage', 0)
                                        self.storage.save_block_metrics(peer_block.block_index, peer_block.timestamp, interval, consensus_time, power_usage)
                                    except Exception as e:
                                        print(f"[ANALYTICS] Failed saving block metrics: {e}")
                                    print(f"[SYNC] Added missing block {peer_block.block_index} from {peer['id']}")
                    
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
        print(f"[METRICS] Resource monitoring active - tracking CPU, RAM, and network load during operations")
        
        # Start dashboard in a separate thread
        self.dashboard_thread.start()
        print(f"[METRICS] Dashboard API available at http://0.0.0.0:{self.node_config['dashboard_port']}")
        print(f"[METRICS] Resource metrics endpoints:")
        print(f"  - GET /api/resource-metrics")
        print(f"  - GET /api/operation-metrics")
        print(f"  - GET /api/export/resource-metrics.csv")
        print(f"  - GET /api/export/operation-metrics.csv?operation_type=<type>")
        
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
                
                # Publish metrics with network monitoring
                metrics_data_size = len(str(metrics_to_publish).encode('utf-8'))
                publish_start = time.time()
                self.mqtt_client.publish_metrics(metrics_to_publish)
                publish_duration = time.time() - publish_start
                self.metrics.record_network_operation('publish_metrics', metrics_data_size, publish_duration, True)
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

            # Ensure we have a valid chain before selecting validator
            if not self.blocks:
                print("[PROCESS TX] No blocks in chain yet, waiting...")
                await asyncio.sleep(1)
                continue

            # Use the latest block index as reference for validator selection
            # This ensures all nodes with the same chain length select the same validator
            reference_block_index = self.blocks[-1].block_index
            print(f"[PROCESS TX] Local chain length: {len(self.blocks)}, Latest block index: {reference_block_index}")
            
            current_validator = self.dpos.get_current_validator(
                reference_block_index=reference_block_index
            )
            
            if not current_validator:
                print("[PROCESS TX] No valid validator available, waiting...")
                await asyncio.sleep(2)
                continue
                
            print(f"[PROCESS TX] Current DPoS validator for block {reference_block_index + 1}: {current_validator}")
            print(f"[PROCESS TX] Node ID: {self.node_id}")

            # Normalize current_validator and self.node_id for comparison
            print(f"[PROCESS TX DEBUG] Node ID: {self.node_id.strip().lower()}")
            print(f"[PROCESS TX DEBUG] Current Validator: {current_validator.strip().lower()}")
            
            # Track how long we've been waiting for the current validator
            if not hasattr(self, '_validator_wait_start'):
                self._validator_wait_start = {}
            
            if current_validator.strip().lower() == self.node_id.strip().lower():
                print(f"[PROCESS TX] {self.node_id} is the current validator.")
                # Clear any waiting state
                if reference_block_index in self._validator_wait_start:
                    del self._validator_wait_start[reference_block_index]
                # Proceed with block proposal
            else:
                print(f"[PROCESS TX] {self.node_id} is not the current validator. Waiting for {current_validator}...")
                
                # Track how long we've been waiting for this validator
                wait_key = (reference_block_index, current_validator)
                if wait_key not in self._validator_wait_start:
                    self._validator_wait_start[wait_key] = time.time()
                
                wait_duration = time.time() - self._validator_wait_start[wait_key]
                timeout = self.dpos.block_time * 3  # Allow 3x block_time before failover
                
                # If validator hasn't created block within timeout, sync chain (they might be behind)
                if wait_duration > timeout:
                    print(f"[PROCESS TX] Validator {current_validator} hasn't created block {reference_block_index + 1} after {wait_duration:.2f}s. Triggering chain sync...")
                    del self._validator_wait_start[wait_key]
                    await self._synchronize_chain()
                    await asyncio.sleep(1)
                    continue
                
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

                # Monitor resource usage during block creation
                with self.metrics.monitor_operation('block_creation', f"create_block_{len(self.blocks)}"):
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

                # Publish new block with network monitoring
                block_data = new_block.to_dict()
                block_data_size = len(str(block_data).encode('utf-8'))
                publish_start = time.time()
                self.mqtt_client.publish_block(block_data)
                publish_duration = time.time() - publish_start
                self.metrics.record_network_operation('publish_block', block_data_size, publish_duration, True)
                print(f"[PROCESS TX] Node {self.node_id} published new block: {new_block.hash}")

                # Add block to local chain and save to storage
                self.blocks.append(new_block)
                
                # Monitor database operation during block save
                start_time = time.time()
                self.storage.save_block(new_block)
                self.metrics.record_database_operation('save_block', time.time() - start_time, 1)
                # Persist per-block analytics
                try:
                    # For genesis block (index 0), interval should be 0
                    interval = 0 if new_block.block_index == 0 else new_block.timestamp - previous_block_timestamp
                    consensus_time = new_block.energy_metrics.get('consensus_time', 0)
                    power_usage = new_block.energy_metrics.get('power_usage', 0)
                    
                    # Monitor database operation for block metrics
                    start_time = time.time()
                    self.storage.save_block_metrics(new_block.block_index, new_block.timestamp, interval, consensus_time, power_usage)
                    self.metrics.record_database_operation('save_block_metrics', time.time() - start_time, 1)
                except Exception as e:
                    print(f"[ANALYTICS] Failed saving block metrics for local block {new_block.block_index}: {e}")
                print(f"[PROCESS TX] Block {new_block.hash} added to local chain and saved.")

                # Record metrics for charts
                self.metrics.record_block_time(new_block.timestamp - previous_block_timestamp)
                self.metrics.record_consensus_time(new_block.energy_metrics.get('consensus_time', 0))

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
            # Use shorter sync interval during early blocks to ensure consistency
            chain_length = len(self.blocks)
            if chain_length < 20:
                sync_interval = 10  # Sync every 10 seconds during first 20 blocks
            else:
                sync_interval = RASPBERRY_PI_SETTINGS['sync_interval']
            await asyncio.sleep(sync_interval)

if __name__ == "__main__":
    node = BlockchainNode()
    asyncio.run(node.start())  # Use asyncio.run to execute the coroutine