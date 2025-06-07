import sqlite3
from typing import Any, Dict, List, Optional
import json

# Assuming Block class is available in the consensus module
from consensus.block import Block

class SQLiteStorage:
    def __init__(self, db_path: str = 'blockchain.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Create tables for blocks and state if not exist
        c.execute('''CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_data TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        conn.commit()
        conn.close()

    def save_block(self, block: Block):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO blocks (block_data) VALUES (?)', (json.dumps(block.to_dict()),))
        conn.commit()
        conn.close()

    def get_blocks(self, start_index: int = 0, end_index: int = -1) -> List[Block]:
        """Get blocks within a range. If end_index is -1, get all blocks from start_index."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if end_index == -1:
            c.execute('SELECT block_data FROM blocks WHERE id > ? ORDER BY id ASC', (start_index,))
        else:
            c.execute('SELECT block_data FROM blocks WHERE id > ? AND id <= ? ORDER BY id ASC', 
                     (start_index, end_index))
            
        rows = c.fetchall()
        conn.close()
        return [Block.from_dict(json.loads(row[0])) for row in rows]

    def get_chain_length(self) -> int:
        """Get the total number of blocks in the chain."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM blocks')
        count = c.fetchone()[0]
        conn.close()
        return count

    def get_latest_block(self) -> Optional[Block]:
        """Get the most recent block in the chain."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT block_data FROM blocks ORDER BY id DESC LIMIT 1')
        row = c.fetchone()
        conn.close()
        return Block.from_dict(json.loads(row[0])) if row else None

    def save_state(self, key: str, value: Any):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('REPLACE INTO state (key, value) VALUES (?, ?)', (key, json.dumps(value)))
        conn.commit()
        conn.close()

    def get_state(self, key: str) -> Any:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT value FROM state WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        return json.loads(row[0]) if row else None 