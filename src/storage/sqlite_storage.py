import sqlite3
from typing import Any, Dict, List, Optional
import json
import os

# Assuming Block class is available in the consensus module
from consensus.block import Block

class SQLiteStorage:
    def __init__(self, db_path: str = "blockchain.db"):
        """Initialize SQLite storage with proper error handling."""
        try:
            # Ensure the database path is absolute
            self.db_path = os.path.abspath(db_path)
            
            # Create directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"[STORAGE] Created database directory: {db_dir}")
            
            # Initialize database
            self._init_db()
            
            # Verify table creation
            self._verify_tables()
            
        except Exception as e:
            print(f"[STORAGE] Error initializing storage: {e}")
            raise

    def _init_db(self):
        """Initialize the database with required tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create blocks table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    index INTEGER PRIMARY KEY,
                    timestamp REAL,
                    validator TEXT,
                    previous_hash TEXT,
                    hash TEXT,
                    transactions TEXT,
                    data TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            print(f"[STORAGE] Database initialized at {self.db_path}")
        except Exception as e:
            print(f"[STORAGE] Error initializing database: {e}")
            raise

    def _verify_tables(self):
        """Verify that required tables exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if blocks table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='blocks'")
            if not cursor.fetchone():
                print("[STORAGE] Blocks table not found, creating...")
                self._init_db()
            
            conn.close()
        except Exception as e:
            print(f"[STORAGE] Error verifying tables: {e}")
            raise

    def save_block(self, block: Block):
        """Save a block to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert transactions and data to JSON strings
            transactions_json = json.dumps(block.transactions)
            data_json = json.dumps(block.data)
            
            cursor.execute('''
                INSERT OR REPLACE INTO blocks 
                (index, timestamp, validator, previous_hash, hash, transactions, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                block.index,
                block.timestamp,
                block.validator,
                block.previous_hash,
                block.hash,
                transactions_json,
                data_json
            ))
            
            conn.commit()
            conn.close()
            print(f"[STORAGE] Block {block.index} saved to database")
        except Exception as e:
            print(f"[STORAGE] Error saving block: {e}")
            raise

    def get_block(self, index: int) -> Optional[Block]:
        """Retrieve a block by its index."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM blocks WHERE index = ?', (index,))
            row = cursor.fetchone()
            
            if row:
                # Convert JSON strings back to Python objects
                transactions = json.loads(row[5])
                data = json.loads(row[6])
                
                block = Block(
                    index=row[0],
                    timestamp=row[1],
                    validator=row[2],
                    previous_hash=row[3],
                    transactions=transactions,
                    data=data
                )
                conn.close()
                return block
            conn.close()
            return None
        except Exception as e:
            print(f"[STORAGE] Error retrieving block: {e}")
            raise

    def get_chain_length(self) -> int:
        """Get the current length of the blockchain."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM blocks')
            length = cursor.fetchone()[0]
            
            conn.close()
            return length
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                print("[STORAGE] Blocks table not found, initializing database...")
                self._init_db()
                return 0
            print(f"[STORAGE] Error getting chain length: {e}")
            return 0
        except Exception as e:
            print(f"[STORAGE] Error getting chain length: {e}")
            return 0

    def get_latest_block(self) -> Optional[Block]:
        """Get the latest block in the chain."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM blocks ORDER BY index DESC LIMIT 1')
            row = cursor.fetchone()
            
            if row:
                # Convert JSON strings back to Python objects
                transactions = json.loads(row[5])
                data = json.loads(row[6])
                
                block = Block(
                    index=row[0],
                    timestamp=row[1],
                    validator=row[2],
                    previous_hash=row[3],
                    transactions=transactions,
                    data=data
                )
                conn.close()
                return block
            conn.close()
            return None
        except Exception as e:
            print(f"[STORAGE] Error retrieving latest block: {e}")
            raise

    def get_blocks(self, start_index: int, end_index: int) -> List[Block]:
        """Get a range of blocks from the chain."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM blocks 
                WHERE index >= ? AND index <= ?
                ORDER BY index ASC
            ''', (start_index, end_index))
            
            blocks = []
            for row in cursor.fetchall():
                # Convert JSON strings back to Python objects
                transactions = json.loads(row[5])
                data = json.loads(row[6])
                
                block = Block(
                    index=row[0],
                    timestamp=row[1],
                    validator=row[2],
                    previous_hash=row[3],
                    transactions=transactions,
                    data=data
                )
                blocks.append(block)
            
            conn.close()
            return blocks
        except Exception as e:
            print(f"[STORAGE] Error retrieving blocks: {e}")
            raise

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