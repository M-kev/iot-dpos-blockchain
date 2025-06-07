from collections import defaultdict
import time

class BlockchainMetrics:
    def __init__(self):
        self.metrics = {}
        self.tps_history = []
        self.consensus_time_history = []
        self.block_time_history = []
        self.cpu_history = []
        self.memory_history = []
        self.power_usage_history = []
        
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

    def record_node_metrics(self, node_id: str, metrics_data: Dict[str, Any]):
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


    def get_power_metrics(self) -> Dict[str, float]:
        # This should return aggregated power or local if for single node dashboard
        total_power = sum(node_metrics['power_usage'] for node_metrics in self.all_nodes_metrics.values())
        return {"total_power": total_power}

    def get_blockchain_metrics(self) -> Dict[str, Any]:
        # This will be refined, currently mostly local node's perspective
        return {
            "tps": self.get_tps(),
            "consensus_time_avg": sum(self.consensus_time_history) / len(self.consensus_time_history) if self.consensus_time_history else 0,
            "block_time_avg": sum(self.block_time_history) / len(self.block_time_history) if self.block_time_history else 0
        }

    def get_system_metrics(self) -> Dict[str, Any]:
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
        # This needs to be pulled from total blocks in storage or aggregated
        return 0 # Placeholder for now, needs real value from storage or aggregated from nodes

    def get_all_validators_metrics(self) -> Dict[str, float]:
        """Return the current view of all validators and their stakes."""
        return self.network_validators

    def get_current_elected_validator(self) -> Optional[str]:
        """Return the current elected validator."""
        return self.current_network_validator

    def get_tps(self) -> float:
        # Simple TPS calculation based on transaction count over time, needs more sophistication
        return 0 # Placeholder for now 