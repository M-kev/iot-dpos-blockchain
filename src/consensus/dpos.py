from typing import List, Dict, Any, Optional
import time
import json
from .block import Block
from monitoring.metrics import BlockchainMetrics

class DPoS:
    def __init__(self, max_validators: int = 21, metrics: Optional[BlockchainMetrics] = None):
        self.max_validators = max_validators
        self.validators: Dict[str, float] = {}  # address -> stake
        self.delegates: List[str] = []
        self.block_time = 3  # seconds
        self.energy_threshold = 5.0  # Maximum energy usage threshold
        self.metrics = metrics  # Store the metrics instance
        self.liveness_threshold = 30 # seconds, if a node hasn't reported metrics in this time, consider it offline
        self.last_delegate_update_time = 0.0 # Initialize last update time
        self.delegate_update_interval = 300 # 5 minutes in seconds
        
    def add_validator(self, address: str, stake: float) -> bool:
        """Add a new validator with their stake."""
        if len(self.validators) >= self.max_validators:
            return False
        self.validators[address] = stake
        # No immediate update_delegates here, it's handled by scheduled call
        return True
        
    def remove_validator(self, address: str) -> bool:
        """Remove a validator."""
        if address in self.validators:
            del self.validators[address]
            # No immediate update_delegates here, it's handled by scheduled call
            return True
        return False
        
    def _update_delegates(self, force_update: bool = False) -> None:
        """Update the list of active delegates based on stake.
        Only updates if enough time has passed or if force_update is True."""
        current_time = time.time()
        if not force_update and (current_time - self.last_delegate_update_time < self.delegate_update_interval):
            return # Not time to update yet

        print("[DPoS] Updating delegates based on stake...")
        sorted_validators = sorted(
            self.validators.items(),
            key=lambda x: x[1],
            reverse=True
        )
        print(f"[DPoS] Sorted validators: {sorted_validators}")
        
        # All validators (up to max_validators) are potential delegates, sorted by stake
        self.delegates = [validator_id for validator_id, stake in sorted_validators][:self.max_validators]
        self.last_delegate_update_time = current_time
        print(f"[DPoS] Delegates updated. All potential delegates (sorted by stake): {self.delegates}")

    def get_current_validator(self, reference_index: int) -> Optional[str]:
        """
        Get the current validator based on a reference block's index,
        considering active and live delegates.
        """
        print(f"[DPoS GET VALIDATOR] All potential delegates (from _update_delegates): {self.delegates}")
        if not self.delegates:
            print("[DPoS GET VALIDATOR] No potential delegates available.")
            return None

        active_and_live_delegates = []
        if self.metrics:
            current_system_time = time.time()
            for delegate_id in self.delegates:
                node_metrics = self.metrics.all_nodes_metrics.get(delegate_id)
                if node_metrics and (current_system_time - node_metrics.get('timestamp', 0) < self.liveness_threshold):
                    active_and_live_delegates.append(delegate_id)
                else:
                    status = "no metrics" if not node_metrics else f"stale metrics ({(current_system_time - node_metrics.get('timestamp', 0)):.2f}s ago)"
                    print(f"[DPoS GET VALIDATOR] Excluding {delegate_id} from current validator selection (not live): {status}")
        else:
            # If no metrics instance, consider all current delegates as active (fallback)
            active_and_live_delegates = self.delegates

        print(f"[DPoS GET VALIDATOR] Active and live delegates for selection: {active_and_live_delegates}")
        if not active_and_live_delegates:
            print("[DPoS GET VALIDATOR] No active and live delegates for selection.")
            return None

        # Deterministically select from the active and live delegates
        expected_validator_slot = (reference_index + 1) % len(active_and_live_delegates)
        
        return active_and_live_delegates[expected_validator_slot]

    def is_time_to_propose_block(self, last_block_timestamp: float) -> bool:
        """Check if enough time has passed since the last block to propose a new one."""
        return time.time() >= last_block_timestamp + self.block_time

    def validate_block(self, block: Block, power_usage: float, previous_block_timestamp: float, previous_block_index: int, sync_tolerance: float = 0.0) -> bool:
        """Validate a block based on DPoS rules and energy efficiency."""
        # Check if block was created by a valid delegate
        if block.validator not in self.delegates:
            print(f"[DPoS VALIDATE] Block validator {block.validator} is not in delegates list")
            return False

        # Check if block was created by the current validator
        current_validator = self.get_current_validator(previous_block_index)
        if block.validator != current_validator:
            print(f"[DPoS VALIDATE] Block validator {block.validator} is not the current validator {current_validator}")
            return False

        # Check if block timestamp is greater than previous block timestamp
        # Allow a small tolerance during synchronization
        if block.timestamp <= previous_block_timestamp - sync_tolerance:
            print(f"[DPoS VALIDATE] Block timestamp {block.timestamp} is not strictly greater than previous block timestamp {previous_block_timestamp} (tolerance: {sync_tolerance})")
            return False

        # Check if block index is greater than previous block index
        if block.index <= previous_block_index:
            print(f"[DPoS VALIDATE] Block index {block.index} is not strictly greater than previous block index {previous_block_index}")
            return False

        # Check if block was created within the allowed time window
        current_time = time.time()
        if abs(current_time - block.timestamp) > self.block_time:
            print(f"[DPoS VALIDATE] Block timestamp {block.timestamp} is too far from current time {current_time}")
            return False

        # Check energy efficiency
        if power_usage > self.energy_threshold:
            print(f"[DPoS VALIDATE] Energy usage {power_usage}W exceeds threshold {self.energy_threshold}W")
            return False

        return True
        
    def adjust_block_time(self, network_load: float) -> None:
        """Dynamically adjust block time based on network load."""
        if network_load > 0.8:  # High load
            self.block_time = max(1, self.block_time - 0.5)
        elif network_load < 0.3:  # Low load
            self.block_time = min(5, self.block_time + 0.5)
            
    def get_validator_stats(self) -> Dict[str, Any]:
        """Get statistics about validators."""
        return {
            'total_validators': len(self.validators),
            'active_delegates': len(self.delegates),
            'block_time': self.block_time,
            'validator_list': self.delegates
        }
    # ... existing code ... 