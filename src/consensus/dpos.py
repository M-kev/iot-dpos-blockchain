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
        # Liveness threshold: Allow 2-3 missed metric intervals (metrics publish every 5s)
        # This ensures offline detection within ~15 seconds
        self.liveness_threshold = 15 # seconds, if a node hasn't reported metrics in this time, consider it offline
        self.last_delegate_update_time = 0.0 # Initialize last update time
        self.delegate_update_interval = 300 # 5 minutes in seconds
        # Grace period for startup: allow nodes that haven't sent metrics yet during first N blocks
        self.startup_grace_blocks = 10  # Blocks during which we're more lenient with liveness
        
        # Checkpoint management
        self.checkpoints: Dict[int, Dict[str, Any]] = {}  # block_height -> checkpoint_data
        self.checkpoint_interval = 100  # Create checkpoint every 100 blocks
        
    def add_validator(self, address: str, stake: float) -> bool:
        """Add a new validator with their stake."""
        if len(self.validators) >= self.max_validators:
            return False
        self.validators[address] = stake
        return True
        
    def remove_validator(self, address: str) -> bool:
        """Remove a validator."""
        if address in self.validators:
            del self.validators[address]
            return True
        return False
        
    def update_stake(self, address: str, new_stake: float) -> bool:
        if address not in self.validators:
            return False
        self.validators[address] = new_stake
        self._update_delegates(force_update=True)
        return True
        
    def _update_delegates(self, force_update: bool = False) -> None:
        """Update the list of active delegates based on stake.
        Only updates if enough time has passed or if force_update is True."""
        current_time = time.time()
        if not force_update and (current_time - self.last_delegate_update_time < self.delegate_update_interval):
            return # Not time to update yet

        print("[DPoS] Updating delegates based on stake...")
        sorted_validators = sorted(
            self.validators.items(),
            key=lambda x: (-x[1], x[0])  # Sort by stake DESC, then node_id ASC
        )
        print(f"[DPoS] Sorted validators: {sorted_validators}")

        # All validators (up to max_validators) are potential delegates, sorted by stake
        self.delegates = [validator_id for validator_id, stake in sorted_validators][:self.max_validators]
        self.last_delegate_update_time = current_time
        print(f"[DPoS] Delegates updated. All potential delegates (sorted by stake): {self.delegates}")

    def get_current_validator(self, reference_block_index: int) -> Optional[str]:
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
            # During startup grace period (first N blocks), be slightly more lenient
            in_startup_grace = reference_block_index < self.startup_grace_blocks
            grace_threshold = self.liveness_threshold * 2 if in_startup_grace else self.liveness_threshold
            
            print(f"[DPoS GET VALIDATOR] Current system time: {current_system_time}")
            print(f"[DPoS GET VALIDATOR] Block index {reference_block_index}, startup grace: {in_startup_grace}, liveness threshold: {grace_threshold}s")
            
            for delegate_id in self.delegates:
                node_metrics = self.metrics.all_nodes_metrics.get(delegate_id)
                
                # Check if node has sent metrics (timestamp > 0 means it has actually sent data)
                has_metrics = node_metrics and node_metrics.get('timestamp', 0) > 0
                
                if has_metrics:
                    time_since_last_metrics = current_system_time - node_metrics.get('timestamp', 0)
                    if time_since_last_metrics < grace_threshold:
                        active_and_live_delegates.append(delegate_id)
                        print(f"[DPoS GET VALIDATOR] Including {delegate_id} as live (last seen: {time_since_last_metrics:.2f}s ago)")
                    else:
                        print(f"[DPoS GET VALIDATOR] Excluding {delegate_id} from current validator selection (stale metrics: {time_since_last_metrics:.2f}s ago, threshold: {grace_threshold}s)")
                else:
                    # Node has never sent metrics - exclude from selection
                    # Even during grace period, we should only select nodes that have sent at least one metric
                    # This prevents offline nodes from blocking progress
                    print(f"[DPoS GET VALIDATOR] Excluding {delegate_id} from current validator selection (no metrics ever received - node may be offline)")
        else:
            # If no metrics instance, consider all current delegates as active (fallback)
            active_and_live_delegates = self.delegates
            print(f"[DPoS GET VALIDATOR] No metrics instance, using all delegates: {active_and_live_delegates}")

        # Sort active and live delegates deterministically by node ID
        active_and_live_delegates = sorted(active_and_live_delegates)

        print(f"[DPoS GET VALIDATOR] Active and live delegates for selection: {active_and_live_delegates}")
        if not active_and_live_delegates:
            print("[DPoS GET VALIDATOR] No active and live delegates for selection.")
            return None

        # Deterministically select from the active and live delegates
        print(f"[DPoS DEBUG] Delegates: {self.delegates}")
        print(f"[DPoS DEBUG] Reference block_index: {reference_block_index}")
        print(f"[DPoS DEBUG] Number of active delegates: {len(active_and_live_delegates)}")
        expected_validator_slot = (reference_block_index + 1) % len(active_and_live_delegates)
        print(f"[DPoS DEBUG] Expected validator slot: {expected_validator_slot}")
        selected_validator = active_and_live_delegates[expected_validator_slot]
        print(f"[DPoS DEBUG] Selected validator: {selected_validator}")
        return selected_validator

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

        # Check if block_index is greater than previous block_index
        if block.block_index <= previous_block_index:
            print(f"[DPoS VALIDATE] Block block_index {block.block_index} is not strictly greater than previous block_index {previous_block_index}")
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
        
    def create_checkpoint(self, block_height: int) -> None:
        """Create a checkpoint at the specified block height."""
        if block_height % self.checkpoint_interval == 0:  # Checkpoint every N blocks
            checkpoint_data = {
                'block_height': block_height,
                'delegates': self.delegates.copy(),
                'validators': self.validators.copy(),
                'timestamp': time.time()
            }
            self.checkpoints[block_height] = checkpoint_data
            print(f"[DPoS] Created checkpoint at block height {block_height}")
            
    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Get the latest checkpoint data."""
        if not self.checkpoints:
            return None
        latest_height = max(self.checkpoints.keys())
        return self.checkpoints[latest_height]
        
    def restore_from_checkpoint(self, block_height: int) -> bool:
        """Restore DPoS state from a checkpoint at the specified block height."""
        if block_height not in self.checkpoints:
            return False
            
        checkpoint = self.checkpoints[block_height]
        self.delegates = checkpoint['delegates'].copy()
        self.validators = checkpoint['validators'].copy()
        print(f"[DPoS] Restored state from checkpoint at block height {block_height}")
        return True
        
    def get_checkpoint_info(self) -> Dict[str, Any]:
        """Get information about all checkpoints."""
        return {
            'total_checkpoints': len(self.checkpoints),
            'checkpoint_heights': sorted(self.checkpoints.keys()),
            'latest_checkpoint': self.get_latest_checkpoint()
        }