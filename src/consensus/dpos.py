from typing import List, Dict, Any, Optional
import time
import json
from .block import Block

class DPoS:
    def __init__(self, max_validators: int = 21):
        self.max_validators = max_validators
        self.validators: Dict[str, float] = {}  # address -> stake
        self.delegates: List[str] = []
        self.block_time = 3  # seconds
        self.last_block_time = 0
        self.energy_threshold = 0.8  # Maximum energy usage threshold
        
    def add_validator(self, address: str, stake: float) -> bool:
        """Add a new validator with their stake."""
        if len(self.validators) >= self.max_validators:
            return False
        self.validators[address] = stake
        self._update_delegates()
        return True
        
    def remove_validator(self, address: str) -> bool:
        """Remove a validator."""
        if address in self.validators:
            del self.validators[address]
            self._update_delegates()
            return True
        return False
        
    def _update_delegates(self) -> None:
        """Update the list of active delegates based on stake."""
        sorted_validators = sorted(
            self.validators.items(),
            key=lambda x: x[1],
            reverse=True
        )
        self.delegates = [v[0] for v in sorted_validators[:self.max_validators]]
        
    def get_current_validator(self) -> Optional[str]:
        """Get the current validator based on time."""
        if not self.delegates:
            return None
            
        current_time = time.time()
        if current_time - self.last_block_time < self.block_time:
            return None
            
        slot = int((current_time - self.last_block_time) / self.block_time)
        return self.delegates[slot % len(self.delegates)]
        
    def validate_block(self, block: Block, energy_usage: float) -> bool:
        """Validate a block considering energy efficiency."""
        if energy_usage > self.energy_threshold:
            return False
            
        current_validator = self.get_current_validator()
        if not current_validator or block.validator != current_validator:
            return False
            
        # Update last block time
        self.last_block_time = time.time()
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