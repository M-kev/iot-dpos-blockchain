from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import List, Dict, Any

@dataclass
class Block:
    block_index: int
    timestamp: float
    transactions: List[Dict[str, Any]]
    previous_hash: str
    validator: str
    energy_metrics: Dict[str, float]
    
    def __post_init__(self):
        self.hash = self.calculate_hash()
        
    def calculate_hash(self) -> str:
        """Calculate the block hash using SHA-256."""
        block_string = json.dumps({
            'block_index': self.block_index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'validator': self.validator,
            'energy_metrics': self.energy_metrics
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary for serialization."""
        return {
            'block_index': self.block_index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'hash': self.hash,
            'validator': self.validator,
            'energy_metrics': self.energy_metrics
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        """Create a Block instance from a dictionary."""
        return cls(
            block_index=data['block_index'],
            timestamp=data['timestamp'],
            transactions=data['transactions'],
            previous_hash=data['previous_hash'],
            validator=data['validator'],
            energy_metrics=data['energy_metrics']
        ) 