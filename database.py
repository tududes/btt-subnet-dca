import sqlite3
from datetime import datetime, timedelta
import os

class SubnetDCADatabase:
    def __init__(self, db_path="subnet_dca.db"):
        """Initialize database connection and create tables if they don't exist"""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        """Create necessary tables if they don't exist"""
        with self.conn:
            # Wallets table to track all wallets we've seen
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS wallets (
                    id INTEGER PRIMARY KEY,
                    coldkey TEXT NOT NULL,
                    hotkey TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(coldkey, hotkey)
                )
            ''')

            # Transactions table for all stake/unstake operations
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    wallet_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    operation TEXT NOT NULL,  -- 'stake' or 'unstake'
                    amount_tao REAL NOT NULL,
                    amount_alpha REAL,
                    price_tao REAL NOT NULL,
                    ema_price_tao REAL NOT NULL,
                    price_diff_pct REAL NOT NULL,
                    slippage_tao REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    test_mode BOOLEAN NOT NULL,
                    FOREIGN KEY(wallet_id) REFERENCES wallets(id)
                )
            ''')

            # Balances table to track balance changes
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS balances (
                    id INTEGER PRIMARY KEY,
                    wallet_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tao_balance REAL NOT NULL,
                    alpha_stake REAL NOT NULL,
                    FOREIGN KEY(wallet_id) REFERENCES wallets(id)
                )
            ''')

    def get_or_create_wallet(self, coldkey: str, hotkey: str) -> int:
        """Get wallet ID or create if not exists"""
        with self.conn:
            # First try to get existing wallet
            cursor = self.conn.execute(
                'SELECT id FROM wallets WHERE coldkey = ? AND hotkey = ?',
                (coldkey, hotkey)
            )
            result = cursor.fetchone()
            
            if result:
                return result[0]
            
            # If not found, create new wallet and return its ID
            cursor = self.conn.execute(
                'INSERT INTO wallets (coldkey, hotkey) VALUES (?, ?)',
                (coldkey, hotkey)
            )
            self.conn.commit()  # Make sure the insert is committed
            return cursor.lastrowid

        # If we somehow got here without a valid ID, raise an error
        raise Exception(f"Failed to get or create wallet for {coldkey[:10]}... / {hotkey[:10]}...")

    def log_transaction(self, coldkey: str, hotkey: str, operation: str, 
                       amount_tao: float, amount_alpha: float, price_tao: float,
                       ema_price: float, slippage: float, success: bool,
                       error_msg: str = None, test_mode: bool = False):
        """Log a stake/unstake transaction"""
        wallet_id = self.get_or_create_wallet(coldkey, hotkey)
        price_diff = (price_tao - ema_price) / ema_price

        with self.conn:
            self.conn.execute('''
                INSERT INTO transactions (
                    wallet_id, operation, amount_tao, amount_alpha, 
                    price_tao, ema_price_tao, price_diff_pct, slippage_tao,
                    success, error_message, test_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (wallet_id, operation, amount_tao, amount_alpha, price_tao,
                 ema_price, price_diff, slippage, success, error_msg, test_mode))

    def update_balances(self, coldkey: str, hotkey: str, tao_balance: float, alpha_stake: float):
        """Update current balances for a wallet"""
        wallet_id = self.get_or_create_wallet(coldkey, hotkey)
        with self.conn:
            self.conn.execute('''
                INSERT INTO balances (wallet_id, tao_balance, alpha_stake)
                VALUES (?, ?, ?)
            ''', (wallet_id, tao_balance, alpha_stake))

    def get_wallet_stats(self, coldkey: str, period: str = '24h'):
        """Get wallet statistics for a given time period"""
        periods = {
            '24h': 'timestamp >= datetime("now", "-1 day")',
            '7d': 'timestamp >= datetime("now", "-7 days")',
            '30d': 'timestamp >= datetime("now", "-30 days")',
            'all': '1=1'
        }
        where_clause = periods.get(period, periods['24h'])

        query = f'''
            WITH wallet_ids AS (
                SELECT id FROM wallets WHERE coldkey = ?
            )
            SELECT 
                COUNT(*) as total_transactions,
                SUM(CASE WHEN operation = 'stake' THEN amount_tao ELSE 0 END) as total_staked,
                SUM(CASE WHEN operation = 'unstake' THEN amount_tao ELSE 0 END) as total_unstaked,
                SUM(CASE WHEN operation = 'stake' THEN amount_alpha ELSE 0 END) as total_alpha_staked,
                SUM(CASE WHEN operation = 'unstake' THEN amount_alpha ELSE 0 END) as total_alpha_unstaked,
                AVG(price_tao) as avg_price,
                AVG(price_diff_pct) as avg_price_diff,
                COUNT(CASE WHEN success = 1 THEN 1 END) as successful_txs,
                COUNT(CASE WHEN success = 0 THEN 1 END) as failed_txs
            FROM transactions t
            JOIN wallet_ids w ON t.wallet_id = w.id
            WHERE {where_clause}
        '''
        
        cursor = self.conn.execute(query, (coldkey,))
        return cursor.fetchone()

    def close(self):
        """Close database connection"""
        self.conn.close() 