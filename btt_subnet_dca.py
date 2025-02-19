import asyncio
import sys
import os
import argparse
from datetime import datetime, timedelta, timezone
import getpass  # Add this import at the top
from utils.database import SubnetDCADatabase
from reports import SubnetDCAReports
from utils.password_manager import WalletPasswordManager

# Constants
SUBTENSOR = 'finney' # or use a local subtensor via ws://127.0.0.1:9944
BLOCK_TIME_SECONDS = 12   
SLIPPAGE_PRECISION = 0.0001  # Precision of 0.0001 tao ($0.05 in slippage for $500 TAO)

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='''
🤖 Bittensor Subnet DCA (dTAO) bot for automated staking/unstaking based on EMA.
This script will chase the EMA of the price of TAO and:
📈 Stake TAO when the price is below the EMA
📉 Unstake TAO when the price is above the EMA

💡 Example usage:
  python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.0001 --budget 1 --min-price-diff 0.05 --test
  python3 btt_subnet_dca.py --rotate-all-wallets --netuid 19 --slippage 0.0001 --budget 0 --test
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog='btt_subnet_dca.py'
    )
    
    # Add rotate-all-wallets mode
    parser.add_argument(
        '--rotate-all-wallets',
        action='store_true',
        help='🔄 Rotate through all wallets and their hotkeys continuously'
    )

    # Required arguments (some only if not rotating)
    required = parser.add_argument_group('required arguments')
    required.add_argument(
        '--netuid',
        type=int,
        required=True,
        help='🌐 The netuid of the subnet to operate on (e.g., 19 for inference subnet)'
    )
    required.add_argument(
        '--wallet',
        type=str,
        help='💼 The name of your wallet (required unless using --rotate-all-wallets)'
    )
    required.add_argument(
        '--hotkey',
        type=str,
        help='🔑 The name of the hotkey to use (required unless using --rotate-all-wallets)'
    )
    required.add_argument(
        '--slippage',
        type=float,
        required=True,
        help='📊 Target slippage in TAO (e.g., 0.0001). Lower values mean smaller trade sizes'
    )
    required.add_argument(
        '--budget',
        type=float,
        required=True,
        help='💰 Maximum TAO budget to use for trading operations (use 0 for using full balance)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--min-price-diff',
        type=float,
        default=0.0,
        help='📏 Minimum price difference from EMA to operate (e.g., 0.05 for 5%% from EMA)'
    )
    parser.add_argument(
        '--one-way-mode',
        choices=['stake', 'unstake'],
        help='↕️ Restrict operations to only staking or only unstaking (default: both)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='🧪 Run in test mode without making actual transactions (recommended for first run)'
    )
    parser.add_argument(
        '--wallet-password',
        type=str,
        help='🔑 Password for all wallets (required with --rotate-all-wallets)'
    )

    # Print help if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()

    # Validate arguments based on mode
    if args.rotate_all_wallets:
        if args.wallet or args.hotkey:
            parser.error("--wallet and --hotkey should not be used with --rotate-all-wallets")
        if not all([args.netuid, args.slippage, args.budget is not None]):
            parser.error("--netuid, --slippage, and --budget are required")
    else:
        if not all([args.netuid, args.wallet, args.hotkey, args.slippage, args.budget is not None]):
            parser.error("--netuid, --wallet, --hotkey, --slippage, and --budget are required when not using --rotate-all-wallets")
    
    return args

# Parse arguments and set global TEST_MODE
args = parse_arguments()
TEST_MODE = args.test

# Import bittensor after argument parsing to avoid its arguments showing in help
import bittensor as bt

# Initialize database at the start
db = SubnetDCADatabase()

# Add after initializing database
reports = SubnetDCAReports(db)

def get_wallet_groups():
    """Group hotkeys by their coldkey (wallet) and return organized structure"""
    wallet_path = os.path.expanduser('~/.bittensor/wallets/')
    wallet_groups = {}
    
    if not os.path.exists(wallet_path):
        print("❌ No Bittensor wallet directory found")
        return wallet_groups
    
    wallets = sorted([d for d in os.listdir(wallet_path) 
                     if os.path.isdir(os.path.join(wallet_path, d))])
    
    for wallet in wallets:
        hotkey_path = os.path.join(wallet_path, wallet, 'hotkeys')
        if os.path.exists(hotkey_path):
            hotkeys = sorted([f for f in os.listdir(hotkey_path) 
                            if os.path.isfile(os.path.join(hotkey_path, f))])
            if hotkeys:  # Only add wallets that have hotkeys
                wallet_groups[wallet] = hotkeys
    
    return wallet_groups

def initialize_wallets():
    """Initialize and unlock all wallets at startup, collecting passwords once per coldkey"""
    wallet_groups = get_wallet_groups()
    if not wallet_groups:
        print("❌ No wallet/hotkey pairs found")
        sys.exit(1)

    unlocked_wallets = []
    pw_manager = WalletPasswordManager()
    
    print("\n🔐 Initializing wallets for rotation...")
    print("=" * 60)
    
    # Get sorted list of coldkeys for sequential processing
    coldkeys = sorted(wallet_groups.keys())
    
    for coldkey_name in coldkeys:
        hotkeys = wallet_groups[coldkey_name]
        print(f"\n💼 Processing wallet: {coldkey_name} with {len(hotkeys)} hotkeys")

        # Get password from .env or prompt user
        password = pw_manager.get_password(coldkey_name)
        
        # Check for blank password to skip this coldkey
        if not password:
            print(f"⏭️  Skipping coldkey: {coldkey_name}")
            continue
        
        # Try to unlock the coldkey
        try:
            # Create a temporary wallet just to test the password
            test_wallet = bt.wallet(name=coldkey_name, hotkey=hotkeys[0])
            test_wallet.coldkey_file.save_password_to_env(password)
            test_wallet.unlock_coldkey()
            print(f"✅ Successfully unlocked coldkey: {coldkey_name}")
            
            # Now use this password for all hotkeys of this coldkey
            for hotkey in hotkeys:
                try:
                    wallet = bt.wallet(name=coldkey_name, hotkey=hotkey)
                    wallet.coldkey_file.save_password_to_env(password)
                    wallet.unlock_coldkey()
                    unlocked_wallets.append(wallet)
                    print(f"  ✓ Added hotkey: {hotkey}")
                except Exception as e:
                    print(f"  ❌ Error with hotkey {hotkey}: {e}")
                    
        except Exception as e:
            print(f"❌ Error unlocking coldkey {coldkey_name}: {e}")
            pw_manager.clear_password(coldkey_name)  # Clear invalid password
            response = input(f"Continue to next coldkey? [Y/n]: ").lower()
            if response not in ['y', 'yes', '']:
                print("Aborting...")
                sys.exit(1)
            continue
    
    if not unlocked_wallets:
        print("❌ No wallets were successfully unlocked")
        sys.exit(1)
    
    print(f"\n✨ Successfully initialized {len(unlocked_wallets)} wallet/hotkey pairs")
    return unlocked_wallets

async def rotate_wallets(netuid, unlocked_wallets):
    """Continuously rotate through all unlocked wallets"""
    while True:
        if not unlocked_wallets:
            print("❌ No wallets available for rotation")
            return

        for wallet in unlocked_wallets:
            cold_addr = wallet.coldkeypub.ss58_address[:5] + "..."
            hot_addr = wallet.hotkey.ss58_address[:5] + "..."
            print(f"\n🔄 Switching to wallet: cold({cold_addr}) hot({hot_addr})")
            # Run one complete cycle of the EMA chasing for this wallet
            await chase_ema(netuid, wallet)

async def chase_ema(netuid, wallet):
    """Run one cycle of EMA chasing for a wallet"""
    remaining_budget = args.budget  # Initialize remaining budget
    subnet_info_displayed = False
    
    async with bt.AsyncSubtensor(SUBTENSOR) as sub:
        while True:  # Keep the while loop for both modes
            subnet_info = await sub.subnet(netuid)
            
            # Get current balances
            current_stake = await sub.get_stake(
                coldkey_ss58 = wallet.coldkeypub.ss58_address,
                hotkey_ss58 = wallet.hotkey.ss58_address,
                netuid = netuid,
            )
            balance = await sub.get_balance(wallet.coldkeypub.ss58_address)

            alpha_price = float(subnet_info.price.tao)
            moving_price = float(subnet_info.moving_price) * 1e11
            price_diff_pct = abs(alpha_price - moving_price) / moving_price

            # Skip if price difference is less than minimum required
            if price_diff_pct < args.min_price_diff:
                print(f"\n⏳ Price difference ({price_diff_pct:.2%}) < minimum required ({args.min_price_diff:.2%})")
                print("💤 Waiting for larger price movement...")
                await sub.wait_for_block()
                continue

            # Show full details on first run, compact view afterwards
            if not subnet_info_displayed:
                subnet_info_displayed = True
                print("\n📊 Subnet Information (Detailed View)")
                print("=" * 60)
                
                blocks_since_registration = subnet_info.last_step + subnet_info.blocks_since_last_step - subnet_info.network_registered_at
                seconds_since_registration = blocks_since_registration * BLOCK_TIME_SECONDS
                current_time = datetime.now(timezone.utc)
                registered_time = current_time - timedelta(seconds=seconds_since_registration)
                registered_time_str = registered_time.strftime('%Y-%m-%d %H:%M:%S UTC')

                info_dict = {
                    '🌐 Network': [
                        ('Netuid', subnet_info.netuid),
                        ('Subnet', subnet_info.subnet_name),
                        ('Symbol', subnet_info.symbol)
                    ],
                    '👤 Ownership': [
                        ('Owner Hotkey', subnet_info.owner_hotkey),
                        ('Owner Coldkey', subnet_info.owner_coldkey),
                        ('Registered', registered_time_str)
                    ],
                    '⚙️ Status': [
                        ('Is Dynamic', subnet_info.is_dynamic),
                        ('Tempo', subnet_info.tempo),
                        ('Last Step', subnet_info.last_step),
                        ('Blocks Since Last Step', subnet_info.blocks_since_last_step)
                    ],
                    '📈 Market': [
                        ('Subnet Volume (Alpha)', str(subnet_info.subnet_volume)),
                        ('Subnet Volume (Tao)', str(subnet_info.subnet_volume * alpha_price)),
                        ('Emission', f"{float(subnet_info.tao_in_emission * 1e2):.2f}%"),
                        ('Price (Tao)', f"{float(alpha_price):.5f}"),
                        ('Moving Price (Tao)', f"{float(moving_price):.5f}")
                    ]
                }
                
                for section, items in info_dict.items():
                    print(f"\n{section}")
                    print("-" * 60)
                    for key, value in items:
                        print(f"{key:25}: {value}")
                print("=" * 60)
            else:
                # Compact view for subsequent runs
                print("\n📊 Status Update")
                print("-" * 40)
                compact_info = [
                    ('Last Step', subnet_info.last_step),
                    ('Blocks Since Last Step', subnet_info.blocks_since_last_step),
                    ('Volume (α)', f"{float(subnet_info.subnet_volume):.2f}"),
                    ('Volume (τ)', f"{float(subnet_info.subnet_volume * alpha_price):.2f}"),
                    ('Price (τ)', f"{float(alpha_price):.5f}"),
                    ('EMA (τ)', f"{float(moving_price):.5f}"),
                    ('Diff', f"{((alpha_price - moving_price) / moving_price):.2%}")
                ]
                for key, value in compact_info:
                    print(f"{key:20}: {value}")
                print("-" * 40)

            # Set max_increment based on budget or available balance
            if args.budget == 0:
                if alpha_price > moving_price:  # Unstaking
                    # Convert current stake to TAO to get maximum available
                    stake_conversion = subnet_info.alpha_to_tao_with_slippage(alpha=float(current_stake))
                    max_increment = float(stake_conversion[0].tao + stake_conversion[1].tao)
                else:  # Staking
                    max_increment = float(balance)
            else:
                max_increment = remaining_budget

            if max_increment <= 0:
                print("❌ No funds available for trading")
                break

            # Rest of the binary search code remains the same
            target_slippage = args.slippage
            min_increment = 0.0
            best_increment = 0.0
            closest_slippage = float('inf')
            
            print("\n🔍 Finding optimal trade size...")
            while (max_increment - min_increment) > 1e-6:
                current_increment = (min_increment + max_increment) / 2
                slippage_tuple = subnet_info.slippage(current_increment)
                slippage = float(slippage_tuple[1].tao)
                print(f"  • Testing {current_increment:.6f} TAO → {slippage:.6f} slippage")
                
                if abs(slippage - target_slippage) < abs(closest_slippage - target_slippage):
                    closest_slippage = slippage
                    best_increment = current_increment
                
                if abs(slippage - target_slippage) < SLIPPAGE_PRECISION:
                    break
                elif slippage < target_slippage:
                    min_increment = current_increment
                else:
                    max_increment = current_increment

            increment = best_increment
            print(f"\n💫 Trade Parameters")
            print("-" * 40)
            print(f"{'Size':20}: {increment:.6f} TAO")
            print(f"{'Slippage':20}: {float(subnet_info.slippage(increment)[1].tao):.6f} TAO")
            if args.budget > 0:
                print(f"{'Budget Left':20}: {remaining_budget:.6f} TAO")
            else:
                if alpha_price > moving_price:
                    print(f"{'Stake Available':20}: {current_stake} α")
                else:
                    print(f"{'Balance Available':20}: {balance} τ")
            print("-" * 40)

            if args.budget > 0 and increment > remaining_budget:
                print("❌ Insufficient remaining budget")
                break

            # Only decrement budget if we're using it
            if args.budget > 0:
                remaining_budget -= abs(increment)

            if alpha_price > moving_price:
                if args.one_way_mode == 'stake':
                    print("⏭️  Price above EMA but stake-only mode active. Skipping...")
                    await sub.wait_for_block()
                    continue
                    
                print(f"\n📉 Price above EMA - UNSTAKING cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
                
                # Convert alpha amount to TAO equivalent including slippage
                alpha_amount = increment / alpha_price  # Convert TAO to alpha
                tao_conversion = subnet_info.alpha_to_tao_with_slippage(alpha=alpha_amount)
                total_tao_impact = float(tao_conversion[0].tao + tao_conversion[1].tao)  # Main amount + slippage
                
                # Only check against budget if we're using it
                if args.budget > 0 and total_tao_impact > remaining_budget:
                    print(f"❌ Unstaking {alpha_amount} α would result in {total_tao_impact} τ impact, exceeding budget of {remaining_budget} τ")
                    break

                if not TEST_MODE:
                    try:
                        await sub.unstake( 
                            wallet = wallet, 
                            netuid = netuid,
                            amount = bt.Balance.from_float(alpha_amount), 
                        )
                        db.log_transaction(
                            coldkey=wallet.coldkeypub.ss58_address,
                            hotkey=wallet.hotkey.ss58_address,
                            operation='unstake',
                            amount_tao=total_tao_impact,
                            amount_alpha=alpha_amount,
                            price_tao=alpha_price,
                            ema_price=moving_price,
                            slippage=float(tao_conversion[1].tao),
                            success=True,
                            test_mode=TEST_MODE
                        )
                        print(f"✅ Successfully unstaked {alpha_amount:.6f} α ≈ {total_tao_impact:.6f} τ @ {alpha_price:.6f} from cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
                        if args.budget > 0:
                            remaining_budget -= total_tao_impact
                    except Exception as e:
                        db.log_transaction(
                            coldkey=wallet.coldkeypub.ss58_address,
                            hotkey=wallet.hotkey.ss58_address,
                            operation='unstake',
                            amount_tao=total_tao_impact,
                            amount_alpha=alpha_amount,
                            price_tao=alpha_price,
                            ema_price=moving_price,
                            slippage=float(tao_conversion[1].tao),
                            success=False,
                            error_msg=str(e),
                            test_mode=TEST_MODE
                        )
                        print(f"❌ Error unstaking: {e}")
                else:
                    print(f"🧪 TEST MODE: Would have unstaked {alpha_amount:.6f} α ≈ {total_tao_impact:.6f} τ from cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
                    if args.budget > 0:
                        remaining_budget -= total_tao_impact

            elif alpha_price < moving_price:
                if args.one_way_mode == 'unstake':
                    print("⏭️  Price below EMA but unstake-only mode active. Skipping...")
                    await sub.wait_for_block()
                    continue
                    
                print(f"\n📈 Price below EMA - STAKING cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")

                # Only check against budget if we're using it
                if args.budget > 0 and increment > remaining_budget:
                    print("❌ Insufficient remaining budget")
                    break

                if not TEST_MODE:
                    try:
                        await sub.add_stake( 
                            wallet = wallet, 
                            netuid = netuid,
                            amount = bt.Balance.from_tao(increment), 
                        )
                        db.log_transaction(
                            coldkey=wallet.coldkeypub.ss58_address,
                            hotkey=wallet.hotkey.ss58_address,
                            operation='stake',
                            amount_tao=increment,
                            amount_alpha=increment/alpha_price,  # Convert TAO to alpha
                            price_tao=alpha_price,
                            ema_price=moving_price,
                            slippage=float(subnet_info.slippage(increment)[1].tao),
                            success=True,
                            test_mode=TEST_MODE
                        )
                        print(f"✅ Successfully staked {increment:.6f} TAO @ {alpha_price:.6f} to cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
                        if args.budget > 0:
                            remaining_budget -= increment
                    except Exception as e:
                        db.log_transaction(
                            coldkey=wallet.coldkeypub.ss58_address,
                            hotkey=wallet.hotkey.ss58_address,
                            operation='stake',
                            amount_tao=increment,
                            amount_alpha=increment/alpha_price,
                            price_tao=alpha_price,
                            ema_price=moving_price,
                            slippage=float(subnet_info.slippage(increment)[1].tao),
                            success=False,
                            error_msg=str(e),
                            test_mode=TEST_MODE
                        )
                        print(f"❌ Error staking: {e}")
                else:
                    print(f"🧪 TEST MODE: Would have staked {increment:.6f} TAO to cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
                    if args.budget > 0:
                        remaining_budget -= increment

            else:
                print("🦄 Price equals EMA - No action needed")
                continue  # Don't decrement budget if no action taken

            current_stake = await sub.get_stake(
                coldkey_ss58 = wallet.coldkeypub.ss58_address,
                hotkey_ss58 = wallet.hotkey.ss58_address,
                netuid = netuid,
            )

            balance = await sub.get_balance(wallet.coldkeypub.ss58_address)
            print(f"\n💰 Wallet Status")
            print("-" * 40)
            print(f"{'Balance':20}: {balance}τ")
            print(f"{'Stake':20}: {current_stake}{subnet_info.symbol}")
            print("-" * 40)

            # Update balances after each operation
            db.update_balances(
                coldkey=wallet.coldkeypub.ss58_address,
                hotkey=wallet.hotkey.ss58_address,
                tao_balance=float(balance),
                alpha_stake=float(current_stake)
            )

            # After successful operation or skip
            if args.rotate_all_wallets:
                print("\n⏭️ Moving to next wallet...")
                print("\n📈 Activity Summary")
                reports.print_summary()
                reports.print_wallet_summary(wallet.coldkeypub.ss58_address)
                return
            
            # For single wallet mode, continue to next block
            print("\n⏳ Waiting for next block...")
            await sub.wait_for_block()

        if args.budget > 0:
            print(f"\n✨ Budget exhausted. Total used: {args.budget - remaining_budget:.6f} TAO")
        else:
            print(f"\n✨ Available balance/stake exhausted")

async def main():
    if args.rotate_all_wallets:
        # Initialize all wallets first
        unlocked_wallets = initialize_wallets()
        while True:
            await rotate_wallets(args.netuid, unlocked_wallets)
    else:
        # Original single wallet mode
        while True:
            await chase_ema(args.netuid, wallet)

# Main execution
if args.rotate_all_wallets:
    asyncio.run(main())
else:
    # Original single wallet mode
    try:
        print(f"🔑 Accessing wallet: {args.wallet} with hotkey: {args.hotkey} for local use only.")
        wallet = bt.wallet(name=args.wallet, hotkey=args.hotkey)
        wallet.unlock_coldkey()
        asyncio.run(main())
    except Exception as e:
        print(f"\nError accessing wallet: {e}")
        sys.exit(1)