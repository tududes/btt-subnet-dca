from utils.database import SubnetDCADatabase
from datetime import datetime, timedelta
import statistics
import argparse
import sys

class SubnetDCAReports:
    def __init__(self, db: SubnetDCADatabase):
        self.db = db

    def get_time_segment_stats(self, hours: int, include_test_mode: bool = False):
        """Get statistics for a specific time segment"""
        query = '''
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp) as hour,
                COUNT(*) as tx_count,
                SUM(CASE WHEN operation = 'stake' THEN amount_tao ELSE 0 END) as staked,
                SUM(CASE WHEN operation = 'unstake' THEN amount_tao ELSE 0 END) as unstaked,
                AVG(price_tao) as avg_price,
                MIN(price_tao) as min_price,
                MAX(price_tao) as max_price,
                AVG(price_diff_pct) as avg_diff,
                AVG(slippage_tao) as avg_slippage,
                COUNT(CASE WHEN success = 1 THEN 1 END) as successful_txs,
                COUNT(CASE WHEN success = 0 THEN 1 END) as failed_txs
            FROM transactions
            WHERE timestamp >= datetime('now', '-' || ? || ' hours')
            AND (test_mode = ? OR test_mode IS NULL)
            GROUP BY strftime('%Y-%m-%d %H:00', timestamp)
            ORDER BY hour DESC
        '''
        cursor = self.db.conn.execute(query, (hours, include_test_mode))
        return cursor.fetchall()

    def print_summary(self, hours_segments=[6, 12, 24, 48, 72], include_test_mode: bool = False):
        """Print summary for different time segments"""
        mode_str = "Test Mode" if include_test_mode else "Live Mode"
        print(f"\n📊 Subnet DCA Activity Summary ({mode_str})")
        print("=" * 80)

        for hours in hours_segments:
            stats = self.get_time_segment_stats(hours, include_test_mode)
            if not stats:
                continue

            total_staked = sum(row[2] or 0 for row in stats)
            total_unstaked = sum(row[3] or 0 for row in stats)
            avg_prices = [row[4] for row in stats if row[4]]
            price_diffs = [row[7] for row in stats if row[7]]
            slippages = [row[8] for row in stats if row[8]]
            successful_txs = sum(row[9] or 0 for row in stats)
            failed_txs = sum(row[10] or 0 for row in stats)

            print(f"\n🕒 Last {hours} Hours")
            print("-" * 80)
            print(f"{'Metric':25} | {'Value':20} | {'Details'}")
            print("-" * 80)
            print(f"{'Transactions':25} | {sum(row[1] for row in stats):20.0f} | {successful_txs} successful, {failed_txs} failed")
            print(f"{'Total Staked':25} | {total_staked:20.6f} | τ")
            print(f"{'Total Unstaked':25} | {total_unstaked:20.6f} | τ")
            print(f"{'Net Position':25} | {total_staked - total_unstaked:20.6f} | τ")
            
            if avg_prices:
                print(f"{'Average Price':25} | {statistics.mean(avg_prices):20.6f} | τ")
                print(f"{'Price Range':25} | {min(p for row in stats for p in [row[5]] if p):20.6f} | to {max(p for row in stats for p in [row[6]] if p):.6f} τ")
            
            if price_diffs:
                print(f"{'Average Price Diff':25} | {statistics.mean(price_diffs)*100:19.2f}% | from EMA")

            if slippages:
                print(f"{'Average Slippage':25} | {statistics.mean(slippages):20.6f} | τ")
                print(f"{'Max Slippage':25} | {max(slippages):20.6f} | τ")

            # Simple ASCII chart of activity
            if stats:
                print("\nActivity Chart (each █ = 1 transaction)")
                print("-" * 80)
                for row in stats[:10]:  # Show last 10 hours
                    hour = datetime.strptime(row[0], '%Y-%m-%d %H:00')
                    bar = "█" * min(row[1], 50)  # Limit bar length to 50
                    success_rate = row[9] / row[1] * 100 if row[1] > 0 else 0
                    print(f"{hour.strftime('%Y-%m-%d %H:00'):20} | {bar} ({row[1]} txs, {success_rate:.1f}% success)")

    def get_wallet_stats(self, coldkey: str, period: str = '24h', include_test_mode: bool = False):
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
                COUNT(CASE WHEN success = 0 THEN 1 END) as failed_txs,
                AVG(slippage_tao) as avg_slippage,
                MAX(slippage_tao) as max_slippage
            FROM transactions t
            JOIN wallet_ids w ON t.wallet_id = w.id
            WHERE {where_clause}
            AND (test_mode = ? OR test_mode IS NULL)
        '''
        
        cursor = self.db.conn.execute(query, (coldkey, include_test_mode))
        return cursor.fetchone()

    def print_wallet_summary(self, coldkey: str, include_test_mode: bool = False):
        """Print summary for a specific wallet"""
        mode_str = "Test Mode" if include_test_mode else "Live Mode"
        periods = ['24h', '7d', '30d', 'all']
        
        print(f"\n👛 Wallet Summary for {coldkey[:10]}... ({mode_str})")
        print("=" * 80)
        
        for period in periods:
            stats = self.get_wallet_stats(coldkey, period, include_test_mode)
            if not stats or stats[0] == 0:
                print(f"\n📅 Period: {period}")
                print("-" * 80)
                print(f"{'Metric':25} | {'Value':20} | {'Details'}")
                print("-" * 80)
                print(f"{'No transactions found in this period':^78}")
                continue
                
            print(f"\n📅 Period: {period}")
            print("-" * 80)
            print(f"{'Metric':25} | {'Value':20} | {'Details'}")
            print("-" * 80)
            print(f"{'Total Transactions':25} | {stats[0]:20.0f} | {stats[7] or 0} successful, {stats[8] or 0} failed")
            print(f"{'Total Staked':25} | {stats[1] or 0:20.6f} | τ")
            print(f"{'Total Unstaked':25} | {stats[2] or 0:20.6f} | τ")
            print(f"{'Net Position':25} | {(stats[1] or 0) - (stats[2] or 0):20.6f} | τ")
            if stats[5]:  # If we have price data
                print(f"{'Average Price':25} | {stats[5]:20.6f} | τ")
            if stats[6]:  # If we have price diff data
                print(f"{'Average Price Diff':25} | {stats[6]*100:19.2f}% | from EMA")
            if stats[9]:  # If we have slippage data
                print(f"{'Average Slippage':25} | {stats[9]:20.6f} | τ")
                print(f"{'Max Slippage':25} | {stats[10]:20.6f} | τ")

    def get_all_wallets(self):
        """Get list of all wallets in database"""
        query = '''
            SELECT DISTINCT coldkey 
            FROM wallets 
            ORDER BY first_seen
        '''
        cursor = self.db.conn.execute(query)
        return [row[0] for row in cursor.fetchall()]

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='''
📊 Subnet DCA Report CLI
View statistics and reports from your running DCA bot.

Examples:
  python3 reports.py --summary
  python3 reports.py --wallet 5CnFd... --period 24h
  python3 reports.py --all-wallets
''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show overall activity summary'
    )
    parser.add_argument(
        '--wallet',
        type=str,
        help='Show statistics for specific wallet (provide coldkey address)'
    )
    parser.add_argument(
        '--period',
        choices=['6h', '12h', '24h', '48h', '72h', '7d', '30d', 'all'],
        default='24h',
        help='Time period for statistics'
    )
    parser.add_argument(
        '--all-wallets',
        action='store_true',
        help='Show statistics for all wallets'
    )
    
    args = parser.parse_args()
    
    if not any([args.summary, args.wallet, args.all_wallets]):
        parser.print_help()
        sys.exit(1)
        
    return args

def main():
    args = parse_arguments()
    
    try:
        db = SubnetDCADatabase()
        reports = SubnetDCAReports(db)
        
        if args.summary:
            reports.print_summary()
            
        if args.wallet:
            reports.print_wallet_summary(args.wallet)
            
        if args.all_wallets:
            wallets = reports.get_all_wallets()
            for wallet in wallets:
                reports.print_wallet_summary(wallet)
                print("\n" + "=" * 80)  # Separator between wallets
                
    except Exception as e:
        print(f"❌ Error accessing database: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main() 