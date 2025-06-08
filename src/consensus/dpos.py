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
        self.liveness_threshold = 20 # seconds, if a node hasn't reported metrics in this time, consider it offline
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
        """Update the list of active delegates based on stake and liveness.
        Only updates if enough time has passed or if force_update is True."""
        current_time = time.time()
        if not force_update and (current_time - self.last_delegate_update_time < self.delegate_update_interval):
            return # Not time to update yet

        print("[DPoS] Updating delegates based on stake and liveness...")
        sorted_validators = sorted(
            self.validators.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        active_delegates = []
        for validator_id, stake in sorted_validators:
            if self.metrics:
                node_metrics = self.metrics.all_nodes_metrics.get(validator_id)
                # Only include if metrics exist and are within liveness threshold
                if node_metrics and (current_time - node_metrics.get('timestamp', 0) < self.liveness_threshold):
                    active_delegates.append(validator_id)
            else:
                # If no metrics instance, consider all current validators as active for simplicity
                active_delegates.append(validator_id)

        self.delegates = active_delegates[:self.max_validators]
        self.last_delegate_update_time = current_time
        print(f"[DPoS] Delegates updated. Active delegates: {self.delegates}")

    def get_current_validator(self, reference_index: int) -> Optional[str]:
        """
        Get the current validator based on a reference block's index,
        considering active delegates. This is a purely deterministic calculation based on active delegates.
        """
        if not self.delegates:
            return None

        active_and_live_delegates = []
        if self.metrics:
            current_system_time = time.time()
            for delegate_id in self.delegates:
                node_metrics = self.metrics.all_nodes_metrics.get(delegate_id)
                if node_metrics and (current_system_time - node_metrics.get('timestamp', 0) < self.liveness_threshold):
                    active_and_live_delegates.append(delegate_id)
        else:
            # If no metrics instance, consider all current delegates as active
            active_and_live_delegates = self.delegates

        if not active_and_live_delegates:
            return None

        # Determine the expected validator index for the *next* block in the sequence
        expected_validator_slot = (reference_index + 1) % len(active_and_live_delegates)
        
        return active_and_live_delegates[expected_validator_slot]

    def is_time_to_propose_block(self, last_block_timestamp: float) -> bool:
        """Check if enough time has passed since the last block to propose a new one."""
        return time.time() >= last_block_timestamp + self.block_time

    def validate_block(self, block: Block, energy_usage: float, previous_block_timestamp: float, previous_block_index: int) -> bool:
        """Validate a block considering energy efficiency and validator."""
        print(f"[DPoS VALIDATE] Validating block {block.hash} by {block.validator} (Index: {block.index})")
        print(f"[DPoS VALIDATE] Energy usage: {energy_usage:.2f}W, Threshold: {self.energy_threshold:.2f}W")
        
        if energy_usage > self.energy_threshold:
            print("[DPoS VALIDATE] Validation failed: Energy usage too high.")
            return False
            
        # For genesis block, it's always valid if it's the first block.
        if block.index == 0:
            print("[DPoS VALIDATE] Genesis block validation successful.")
            return True

        # Ensure block timestamp is strictly greater than previous block timestamp to maintain order
        if block.timestamp <= previous_block_timestamp:
            print(f"[DPoS VALIDATE] Validation failed: Block timestamp {block.timestamp} is not strictly greater than previous block timestamp {previous_block_timestamp}.")
            return False

        # For subsequent blocks, compare the block's validator with the expected validator
        # based on the *previous* block in the chain.
        expected_validator = self.get_current_validator(
            reference_index=previous_block_index
        )

        print(f"[DPoS VALIDATE] Block validator: {block.validator}, Expected DPoS validator: {expected_validator}")
        
        if not expected_validator or block.validator != expected_validator:
            print("[DPoS VALIDATE] Validation failed: Validator mismatch or no expected validator for this block's slot.")
            return False

        print("[DPoS VALIDATE] Block validation successful.")
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