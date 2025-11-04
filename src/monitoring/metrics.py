from collections import defaultdict, deque
import time
import psutil
import threading
from contextlib import contextmanager
from typing import Dict, Any, Optional
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
        
        # Rolling window of transaction timestamps (seconds)
        self.transaction_events: deque[float] = deque()
        self.tps_window_seconds: int = 10
        
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
        
        # Resource monitoring during block operations
        self.resource_metrics_history = deque(maxlen=100)  # Keep last 100 operations
        self.operation_metrics = {
            'block_validation': [],
            'block_creation': [],
            'network_operations': [],
            'database_operations': []
        }
        self._resource_lock = threading.Lock()

    def record_block_time(self, value):
        self.block_time_history.append(value)
        if len(self.block_time_history) > 20: # Keep last 20 for chart
            self.block_time_history.pop(0)

    def record_consensus_time(self, value):
        self.consensus_time_history.append(value)
        if len(self.consensus_time_history) > 20:
            self.consensus_time_history.pop(0)

    def record_transactions(self, count):
        """Record 'count' new transactions at the current timestamp for TPS calculation."""
        now = time.time()
        for _ in range(max(0, int(count))):
            self.transaction_events.append(now)
        # Drop events older than the window
        cutoff = now - self.tps_window_seconds
        while self.transaction_events and self.transaction_events[0] < cutoff:
            self.transaction_events.popleft()

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

    def get_system_metrics(self) -> dict:
        # This now returns a dict of all nodes' system metrics
        return {
            node_id: {
                'cpu_percent': data['cpu_percent'],
                'memory_percent': data['memory_percent'],
                'temperature': data['temperature'],
                'power_usage': data['power_usage'],
                'block_count': data.get('block_count', 0),  # Include block count
                'pending_transactions': data.get('pending_transactions', 0),  # Include pending transactions
                'timestamp': data['timestamp']
            } for node_id, data in self.all_nodes_metrics.items()
        }

    def get_cumulative_mining_power(self) -> float:
        """Calculate cumulative power used for mining from genesis to current block."""
        # Get all blocks from storage
        total_blocks = self.get_chain_length()
        if total_blocks == 0:
            return 0.0
        
        # Get blocks from storage to calculate actual cumulative power
        blocks = self.storage.get_blocks(0, total_blocks - 1)
        cumulative_power = 0.0
        
        for block in blocks:
            # Extract power usage from block's energy metrics
            if hasattr(block, 'energy_metrics') and block.energy_metrics:
                power_usage = block.energy_metrics.get('power_usage', 0.5)
                cumulative_power += power_usage
            else:
                # Fallback to estimated power per block
                cumulative_power += 0.5
        
        return cumulative_power

    def get_power_metrics(self) -> dict:
        # Return cumulative mining power instead of current total power
        cumulative_mining_power = self.get_cumulative_mining_power()
        return {"total_power": cumulative_mining_power}

    def get_blockchain_metrics(self) -> dict:
        # This will be refined, currently mostly local node's perspective
        total_blocks = self.get_chain_length()
        return {
            "tps": self.get_tps(),
            "consensus_time_avg": sum(self.consensus_time_history) / len(self.consensus_time_history) if self.consensus_time_history else 0,
            "block_time_avg": sum(self.block_time_history) / len(self.block_time_history) if self.block_time_history else 0,
            "total_blocks": total_blocks # Updated to use get_chain_length
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
        """Compute transactions per second across all nodes over the rolling window."""
        now = time.time()
        cutoff = now - self.tps_window_seconds
        # Trim old events
        while self.transaction_events and self.transaction_events[0] < cutoff:
            self.transaction_events.popleft()
        if not self.transaction_events:
            return 0.0
        window_span = max(1e-6, min(self.tps_window_seconds, (self.transaction_events[-1] - self.transaction_events[0]) or self.tps_window_seconds))
        return len(self.transaction_events) / window_span

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
    
    @contextmanager
    def monitor_operation(self, operation_type: str, operation_id: str = None):
        """Context manager to monitor resource usage during blockchain operations."""
        if operation_id is None:
            operation_id = f"{operation_type}_{int(time.time() * 1000)}"
        
        # Get initial resource state
        initial_cpu = psutil.cpu_percent()
        initial_memory = psutil.virtual_memory()
        initial_network = psutil.net_io_counters()
        start_time = time.time()
        
        try:
            yield operation_id
        finally:
            # Get final resource state
            end_time = time.time()
            final_cpu = psutil.cpu_percent()
            final_memory = psutil.virtual_memory()
            final_network = psutil.net_io_counters()
            
            # Calculate resource usage during operation
            operation_metrics = {
                'operation_id': operation_id,
                'operation_type': operation_type,
                'start_time': start_time,
                'end_time': end_time,
                'duration': end_time - start_time,
                'cpu_usage': {
                    'initial': initial_cpu,
                    'final': final_cpu,
                    'avg': (initial_cpu + final_cpu) / 2
                },
                'memory_usage': {
                    'initial_mb': initial_memory.used / (1024 * 1024),
                    'final_mb': final_memory.used / (1024 * 1024),
                    'peak_mb': final_memory.used / (1024 * 1024),  # Simplified, could track actual peak
                    'memory_delta_mb': (final_memory.used - initial_memory.used) / (1024 * 1024)
                },
                'network_usage': {
                    'bytes_sent': final_network.bytes_sent - initial_network.bytes_sent,
                    'bytes_recv': final_network.bytes_recv - initial_network.bytes_recv,
                    'packets_sent': final_network.packets_sent - initial_network.packets_sent,
                    'packets_recv': final_network.packets_recv - initial_network.packets_recv
                }
            }
            
            # Store metrics in memory and persist to database
            with self._resource_lock:
                self.resource_metrics_history.append(operation_metrics)
                if operation_type in self.operation_metrics:
                    self.operation_metrics[operation_type].append(operation_metrics)
                    # Keep only last 50 operations per type
                    if len(self.operation_metrics[operation_type]) > 50:
                        self.operation_metrics[operation_type].pop(0)
                
                # Persist to database for long-term storage
                try:
                    self.storage.save_resource_operation(operation_metrics)
                except Exception as e:
                    print(f"[METRICS] Error persisting resource operation to database: {e}")
    
    def get_resource_metrics(self) -> Dict[str, Any]:
        """Get comprehensive resource utilization metrics (from database + recent memory)."""
        # Load all operations from database for comprehensive data
        db_operations = self.storage.get_resource_operations(limit=100)  # Get latest 100 from DB
        
        with self._resource_lock:
            # Combine database operations with recent in-memory ones
            # Use a dict to deduplicate by operation_id
            all_operations = {}
            for op in db_operations:
                all_operations[op['operation_id']] = op
            for op in self.resource_metrics_history:
                all_operations[op['operation_id']] = op
            
            recent_operations_list = list(all_operations.values())
            # Sort by start_time descending (most recent first)
            recent_operations_list.sort(key=lambda x: x.get('start_time', 0), reverse=True)
            
            # Build operation summaries by type from database
            operation_summaries = {}
            for op_type in ['block_validation', 'block_creation', 'network_operations', 'database_operations']:
                ops_of_type = self.storage.get_resource_operations(operation_type=op_type)
                if not ops_of_type:
                    continue
                
                # Check if this is a block operation (has cpu_usage, memory_usage, network_usage)
                if op_type in ['block_validation', 'block_creation']:
                    operation_summaries[op_type] = {
                        'count': len(ops_of_type),
                        'avg_duration': sum(op.get('duration', 0) for op in ops_of_type) / len(ops_of_type) if ops_of_type else 0,
                        'avg_cpu': sum(op.get('cpu_usage', {}).get('avg', 0) for op in ops_of_type) / len(ops_of_type) if ops_of_type else 0,
                        'avg_memory_delta': sum(op.get('memory_usage', {}).get('memory_delta_mb', 0) for op in ops_of_type) / len(ops_of_type) if ops_of_type else 0,
                        'total_network_bytes': sum(
                            op.get('network_usage', {}).get('bytes_sent', 0) + 
                            op.get('network_usage', {}).get('bytes_recv', 0) for op in ops_of_type
                        )
                    }
            
            return {
                'recent_operations': recent_operations_list[:100],  # Return latest 100
                'operation_summaries': operation_summaries,
                'current_system_state': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'memory_available_mb': psutil.virtual_memory().available / (1024 * 1024),
                    'disk_usage_percent': psutil.disk_usage('/').percent,
                    'network_io': {
                        'bytes_sent': psutil.net_io_counters().bytes_sent,
                        'bytes_recv': psutil.net_io_counters().bytes_recv
                    }
                }
            }
    
    def get_operation_metrics(self, operation_type: str = None) -> Dict[str, Any]:
        """Get detailed metrics for specific operation types (from database)."""
        # Load from database for persistent storage
        if operation_type:
            return self.storage.get_resource_operations(operation_type=operation_type)
        else:
            # Return all operations by type
            result = {}
            for op_type in ['block_validation', 'block_creation', 'network_operations', 'database_operations']:
                result[op_type] = self.storage.get_resource_operations(operation_type=op_type)
            return result
    
    def record_network_operation(self, operation: str, bytes_transferred: int, duration: float, success: bool = True):
        """Record network operation metrics."""
        network_metrics = {
            'operation': operation,
            'timestamp': time.time(),
            'bytes_transferred': bytes_transferred,
            'duration': duration,
            'success': success,
            'throughput_mbps': (bytes_transferred * 8) / (duration * 1_000_000) if duration > 0 else 0
        }
        
        with self._resource_lock:
            self.operation_metrics['network_operations'].append(network_metrics)
            if len(self.operation_metrics['network_operations']) > 50:
                self.operation_metrics['network_operations'].pop(0)
    
    def record_database_operation(self, operation: str, duration: float, rows_affected: int = 0):
        """Record database operation metrics."""
        db_metrics = {
            'operation': operation,
            'timestamp': time.time(),
            'duration': duration,
            'rows_affected': rows_affected,
            'throughput_rows_per_sec': rows_affected / duration if duration > 0 else 0
        }
        
        with self._resource_lock:
            self.operation_metrics['database_operations'].append(db_metrics)
            if len(self.operation_metrics['database_operations']) > 50:
                self.operation_metrics['database_operations'].pop(0) 