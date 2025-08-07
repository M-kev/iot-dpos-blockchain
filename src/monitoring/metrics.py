from collections import defaultdict
import time
from storage.sqlite_storage import SQLiteStorage
from consensus.block import Block

class BlockchainMetrics:
    def __init__(self, local_node_id: str, storage: SQLiteStorage):
        self.metrics = {}
        self.tps_history = []
        self.consensus_time_history = []
        self.block_time_history = []
        self.cpu_history = []
        self.memory_history = []
        self.power_usage_history = []
        
        self.local_node_id = local_node_id
        self.storage = storage
        
        # New: Store metrics for all nodes
        self.all_nodes_metrics = defaultdict(lambda: {
            'cpu_percent': 0,
            'memory_percent': 0,
            'temperature': 0,
            'power_usage': 0,
            'block_count': 0,
            'pending_transactions': 0,
            'current_stake': 0,
            'is_validator': False,
            'timestamp': 0
        })
        self.network_validators = {}
        self.current_network_validator = None

    def record_block_time(self, value):
        self.block_time_history.append(value)
        if len(self.block_time_history) > 20: # Keep last 20 for chart
            self.block_time_history.pop(0)

    def record_consensus_time(self, value):
        self.consensus_time_history.append(value)
        if len(self.consensus_time_history) > 20:
            self.consensus_time_history.pop(0)

    def record_transactions(self, count):
        # This is more for instantaneous TPS calculation
        pass

    def record_propagation_delay(self, value):
        # For future use or specific tracking
        pass

    def record_node_metrics(self, node_id: str, metrics_data: dict):
        """Record and update metrics for a specific node."""
        self.all_nodes_metrics[node_id].update({
            'cpu_percent': metrics_data.get('cpu_percent', 0),
            'memory_percent': metrics_data.get('memory_percent', 0),
            'temperature': metrics_data.get('temperature', 0),
            'power_usage': metrics_data.get('power_usage', 0),
            'block_count': metrics_data.get('block_count', 0),
            'pending_transactions': metrics_data.get('pending_transactions', 0),
            'current_stake': metrics_data.get('current_stake', 0),
            'timestamp': time.time() # Timestamp of last update
        })
        
        # Update global validator list if included
        if 'all_validators' in metrics_data:
            self.network_validators = metrics_data['all_validators']
        
        # Update current network validator
        if 'current_network_validator' in metrics_data:
            self.current_network_validator = metrics_data['current_network_validator']

    def get_power_metrics(self) -> dict:
        # This should return aggregated power or local if for single node dashboard
        total_power = sum(node_metrics['power_usage'] for node_metrics in self.all_nodes_metrics.values())
        return {"total_power": total_power}

    def get_blockchain_metrics(self) -> dict:
        # This will be refined, currently mostly local node's perspective
        total_blocks = self.get_chain_length()
        return {
            "tps": self.get_tps(),
            "consensus_time_avg": sum(self.consensus_time_history) / len(self.consensus_time_history) if self.consensus_time_history else 0,
            "block_time_avg": sum(self.block_time_history) / len(self.block_time_history) if self.block_time_history else 0,
            "total_blocks": total_blocks # Updated to use get_chain_length
        }

    def get_system_metrics(self) -> dict:
        # This now returns a dict of all nodes' system metrics
        return {
            node_id: {
                'cpu_percent': data['cpu_percent'],
                'memory_percent': data['memory_percent'],
                'temperature': data['temperature'],
                'power_usage': data['power_usage'],
                'timestamp': data['timestamp']
            } for node_id, data in self.all_nodes_metrics.items()
        }

    def get_blockchain_size(self) -> int:
        """Return a proxy for the total blockchain size (e.g., total blocks * average block size)."""
        # This is a rough estimation. A more accurate size would involve serializing and measuring actual blocks.
        total_blocks = self.get_chain_length()
        # Assuming an average block size of 1KB (1024 bytes) as a rough estimate
        # In a real scenario, you'd calculate actual block sizes or store them.
        approx_block_size_bytes = 1024 
        return total_blocks * approx_block_size_bytes # Updated to use total_blocks from get_chain_length

    def get_all_validators_metrics(self) -> dict:
        """Return the current view of all validators and their stakes."""
        return self.network_validators

    def get_current_elected_validator(self) -> str | None:
        """Return the current elected validator."""
        return self.current_network_validator

    def get_tps(self) -> float:
        # Simple TPS calculation based on transaction count over time, needs more sophistication
        return 0 # Placeholder for now 

    def get_chain_length(self) -> int:
        """Return the current length of the blockchain from storage."""
        return self.storage.get_chain_length()

    def get_latest_block_hash(self) -> str | None:
        """Return the hash of the latest block from storage."""
        latest_block = self.storage.get_latest_block()
        return latest_block.hash if latest_block else None

    def get_blocks_from_storage(self, start_block_index: int, end_block_index: int) -> list:
        """Retrieve a range of blocks from storage."""
        return self.storage.get_blocks(start_block_index, end_block_index) 