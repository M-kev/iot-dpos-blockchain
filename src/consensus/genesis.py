from typing import Dict, Any, List
import json
import hashlib
import time
from .block import Block

class GenesisBlock:
    def __init__(self):
        self.initial_stakes = {
            "pi_node_1": 1000,
            "pi_node_2": 1000,
            "pi_node_3": 1000,
            "pi_node_4": 1000,
            "pi_node_5": 1000,
            "pi_node_6": 1000
        }
        self.fixed_timestamp = 1717777777  # Use a constant value for determinism
        
    def create_genesis_block(self) -> Block:
        """Create the genesis block with initial stake distribution."""
        genesis_data = {
            "timestamp": self.fixed_timestamp,
            "transactions": [
                {
                    "type": "stake_distribution",
                    "data": self.initial_stakes,
                    "timestamp": self.fixed_timestamp
                }
            ],
            "energy_metrics": {
                "cpu_percent": 0,
                "memory_percent": 0,
                "temperature": 0,
                "power_usage": 0
            }
        }
        
        # Create genesis block
        genesis_block = Block(
            block_index=0,
            timestamp=genesis_data["timestamp"],
            transactions=genesis_data["transactions"],
            previous_hash="0" * 64,  # First block has no previous hash
            validator="genesis",
            energy_metrics=genesis_data["energy_metrics"]
        )
        
        return genesis_block
        
    def get_initial_stakes(self) -> Dict[str, float]:
        """Get the initial stake distribution."""
        return self.initial_stakes
        
    def save_genesis_block(self, filepath: str = "blockchain_data/genesis.json") -> None:
        """Save genesis block to file."""
        genesis_block = self.create_genesis_block()
        
        # Create directory if it doesn't exist
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(genesis_block.to_dict(), f, indent=4)
            
    @classmethod
    def load_genesis_block(cls, filepath: str = "blockchain_data/genesis.json") -> Block:
        """Load genesis block from file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return Block.from_dict(data)
        except FileNotFoundError:
            # If file doesn't exist, create new genesis block
            genesis = cls()
            genesis.save_genesis_block(filepath)
            return genesis.create_genesis_block()
            
    def verify_genesis_block(self, block: Block) -> bool:
        """Verify if a block matches the genesis block (ignore non-deterministic fields)."""
        genesis_block = self.create_genesis_block()
        return (
            block.block_index == genesis_block.block_index and
            block.previous_hash == genesis_block.previous_hash and
            block.validator == genesis_block.validator and
            block.transactions[0]['type'] == genesis_block.transactions[0]['type'] and
            block.transactions[0]['data'] == genesis_block.transactions[0]['data']
        ) 