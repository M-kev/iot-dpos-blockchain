import sqlite3
from typing import Any, Dict, List
import json

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

    def save_block(self, block: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO blocks (block_data) VALUES (?)', (json.dumps(block),))
        conn.commit()
        conn.close()

    def get_blocks(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT block_data FROM blocks')
        rows = c.fetchall()
        conn.close()
        return [json.loads(row[0]) for row in rows]

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