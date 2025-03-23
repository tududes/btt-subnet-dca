import asyncio
import sys
import os
import argparse
from datetime import datetime, timedelta, timezone
import getpass
from utils.database import SubnetDCADatabase
from reports import SubnetDCAReports
from utils.password_manager import WalletPasswordManager
from utils.settings import SUBTENSOR, BLOCK_TIME_SECONDS, DCA_RESERVE_ALPHA, DCA_RESERVE_TAO, SLIPPAGE_PRECISION, HOLDING_WALLET_NAME, VALIDATOR_HOTKEYS, VALIDATOR_HOTKEY, MIN_UNSTAKE_ALPHA, MIN_TAO_DEFICIT
import signal


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='''
🤖 Bittensor Subnet DCA (dTAO) bot for automated staking/unstaking based on EMA.
This script will chase the EMA of the price of TAO and:
📈 Stake TAO when the price is below the EMA
📉 Unstake TAO when the price is above the EMA

💡 Example usage:
  python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.00001 --budget 1 --min-price-diff 0.05 --test
  python3 btt_subnet_dca.py --rotate-all-wallets --netuid 19 --slippage 0.00001 --budget 0 --test
  python3 btt_subnet_dca.py --harvest-alpha --rotate-all-wallets --netuid 19 --slippage 0.00001 --test
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
        help='📊 Target slippage in TAO (e.g., 0.00001). Lower values mean smaller trade sizes'
    )
    required.add_argument(
        '--budget',
        type=float,
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

    # Add alpha harvest mode
    parser.add_argument(
        '--harvest-alpha',
        action='store_true',
        help='🔄 Harvest excess alpha to maintain TAO reserve (overrides EMA chasing)'
    )

    # Add dynamic slippage option
    parser.add_argument(
        '--dynamic-slippage',
        action='store_true',
        help='📊 Dynamically adjust slippage based on price difference from EMA'
    )
    parser.add_argument(
        '--max-price-diff',
        type=float,
        help='📈 Maximum price difference for dynamic slippage scaling (e.g., 0.20 for 20%%)'
    )

    # Add reserve override options
    parser.add_argument(
        '--alpha-reserve',
        type=float,
        help=f'🔒 Override the minimum alpha balance to maintain (default: {DCA_RESERVE_ALPHA})'
    )
    parser.add_argument(
        '--tao-reserve',
        type=float,
        help=f'🔒 Override the minimum TAO balance to maintain (default: {DCA_RESERVE_TAO})'
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
        if not args.harvest_alpha and not all([args.netuid, args.slippage, args.budget is not None]):
            parser.error("--netuid, --slippage, and --budget are required")
        elif args.harvest_alpha and not all([args.netuid, args.slippage]):
            parser.error("--netuid and --slippage are required with --harvest-alpha")
    else:
        if args.harvest_alpha:
            if not all([args.netuid, args.wallet, args.slippage]):
                parser.error("--netuid, --wallet, and --slippage are required with --harvest-alpha")
            # --hotkey is optional with --harvest-alpha when --wallet is provided
            # If --hotkey is provided, only that specific hotkey will be processed
        elif not all([args.netuid, args.wallet, args.hotkey, args.slippage, args.budget is not None]):
            parser.error("--netuid, --wallet, --hotkey, --slippage, and --budget are required when not using --rotate-all-wallets or --harvest-alpha")
    
    # Validate dynamic slippage arguments
    if args.dynamic_slippage:
        if args.max_price_diff is not None and args.max_price_diff < args.min_price_diff:
            parser.error("--max-price-diff must be greater than --min-price-diff")
    
    return args

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

def initialize_wallets(bt, wallet_name: str = None, hotkey_name: str = None, args: argparse.Namespace = None):
    """Initialize and unlock wallets at startup, collecting passwords once per coldkey.
    
    Args:
        bt: The bittensor module
        wallet_name: Optional name of specific wallet to unlock. If None, unlocks all wallets.
    """
    wallet_groups = get_wallet_groups()
    if not wallet_groups:
        print("❌ No wallet/hotkey pairs found")
        sys.exit(1)

    unlocked_wallets = []
    pw_manager = WalletPasswordManager()
    
    print("\n🔐 Initializing wallets...")
    print("=" * 60)
    
    # Get sorted list of coldkeys for sequential processing
    coldkeys = sorted(wallet_groups.keys())
    
    # Filter to specific wallet if provided
    if wallet_name:
        if wallet_name not in coldkeys:
            print(f"❌ Wallet '{wallet_name}' not found")
            sys.exit(1)
        coldkeys = [wallet_name]
    else:
        # Skip the holding wallet when processing all wallets ONLY in EMA chasing mode (not for alpha harvesting)
        try:
            from utils.settings import HOLDING_WALLET_NAME
            # Check if we're in alpha harvesting mode based on args
            in_alpha_harvest_mode = hasattr(args, 'harvest_alpha') and args.harvest_alpha
            
            # Only skip the holding wallet in EMA chasing mode, not in alpha harvesting mode
            if HOLDING_WALLET_NAME in coldkeys and not in_alpha_harvest_mode:
                print(f"⏭️  Skipping holding wallet: {HOLDING_WALLET_NAME}")
                coldkeys.remove(HOLDING_WALLET_NAME)
        except ImportError:
            pass  # HOLDING_WALLET_NAME not defined, process all wallets
    
    for coldkey_name in coldkeys:
        hotkeys = wallet_groups[coldkey_name]

        if hotkey_name:
            if hotkey_name not in hotkeys:
                print(f"❌ Hotkey '{hotkey_name}' not found in wallet '{coldkey_name}'")
                sys.exit(1)
            hotkeys = [hotkey_name]

        print(f"\n💼 Processing wallet: {coldkey_name} with {len(hotkeys)} hotkeys")

        # Get password from .env or prompt user
        password = pw_manager.get_password(coldkey_name)
        
        # Check for blank password to skip this coldkey
        if not password:
            print(f"⏭️  Skipping coldkey: {coldkey_name}")
            continue
        
        # Try to unlock the coldkey
        try:            
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



def log_operation(db, wallet, operation: str, amount_tao: float, amount_alpha: float, 
                 price_tao: float, ema_price: float, slippage: float, success: bool, 
                 error_msg: str = None, test_mode: bool = False):
    """Helper function to log all operations to database"""
    try:
        db.log_transaction(
            coldkey=wallet.coldkeypub.ss58_address,
            hotkey=wallet.hotkey.ss58_address,
            operation=operation,
            amount_tao=amount_tao,
            amount_alpha=amount_alpha,
            price_tao=price_tao,
            ema_price=ema_price,
            slippage=slippage,
            success=success,
            error_msg=error_msg,
            test_mode=test_mode
        )
    except Exception as e:
        print(f"❌ Error logging transaction: {e}")

async def perform_stake(sub, wallet, netuid, increment, alpha_price, moving_price, subnet_info, test_mode=False):
    """Perform stake operation with error handling and logging"""
    slippage_info = subnet_info.slippage(increment)
    slippage = float(slippage_info[1].tao)
    
    try:
        if not test_mode:
            results = await sub.add_stake(
                wallet=wallet,
                netuid=netuid,
                amount=bt.Balance.from_tao(increment),
            )
            if not results:
                raise Exception("Stake failed")
            
            print(f"✅ Successfully staked {increment:.6f} TAO @ {alpha_price:.6f} to cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
            
            log_operation(
                db=db,
                wallet=wallet,
                operation='stake',
                amount_tao=increment,
                amount_alpha=increment/alpha_price,
                price_tao=alpha_price,
                ema_price=moving_price,
                slippage=slippage,
                success=True,
                test_mode=test_mode
            )
            return True
        else:
            print(f"🧪 TEST MODE: Would have staked {increment:.6f} TAO to cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
            return True
    except Exception as e:
        log_operation(
            db=db,
            wallet=wallet,
            operation='stake',
            amount_tao=increment,
            amount_alpha=increment/alpha_price,
            price_tao=alpha_price,
            ema_price=moving_price,
            slippage=slippage,
            success=False,
            error_msg=str(e),
            test_mode=test_mode
        )
        print(f"❌ Error staking: {e}")
        return False

async def perform_unstake(sub, wallet, netuid, alpha_amount, total_tao_impact, alpha_price, moving_price, test_mode=False):
    """Perform unstake operation with error handling and logging"""
    try:
        # Get current stake from regular hotkey
        current_stake = await sub.get_stake(
            coldkey_ss58=wallet.coldkeypub.ss58_address,
            hotkey_ss58=wallet.hotkey.ss58_address,
            netuid=netuid,
        )
        regular_hotkey_balance = float(current_stake)
        
        # Get stake balances from all validator hotkeys
        validator_balances = []
        total_validator_balance = 0.0
        
        for validator_hotkey in VALIDATOR_HOTKEYS:
            try:
                validator_stake = await sub.get_stake(
                    coldkey_ss58=wallet.coldkeypub.ss58_address,
                    hotkey_ss58=validator_hotkey,
                    netuid=netuid,
                )
                validator_balance = float(validator_stake)
                total_validator_balance += validator_balance
                
                validator_balances.append({
                    'hotkey': validator_hotkey,
                    'balance': validator_balance
                })
                
                print(f"  • Validator hotkey {validator_hotkey[:5]}...: {validator_balance:.6f} α")
            except Exception as e:
                print(f"  ⚠️ Error getting stake for validator {validator_hotkey[:5]}...: {e}")
        
        print(f"Distribution of α:")
        print(f"  • Regular hotkey: {regular_hotkey_balance:.6f} α")
        print(f"  • All validator hotkeys: {total_validator_balance:.6f} α")
        print(f"  • Total: {(regular_hotkey_balance + total_validator_balance):.6f} α")
        print(f"  • Need to unstake: {alpha_amount:.6f} α")
        
        # Sort validator hotkeys by balance (highest first) for efficient unstaking
        validator_balances.sort(key=lambda x: x['balance'], reverse=True)
        
        remaining_unstake = alpha_amount
        total_unstaked = 0.0
        
        # Keep track of slippage for logging
        slippage = 0.0
        
        if not test_mode:
            # First unstake from validator hotkeys in order of balance (highest first)
            for validator_info in validator_balances:
                if remaining_unstake <= 0:
                    break
                
                validator_hotkey = validator_info['hotkey']
                validator_balance = validator_info['balance']
                
                if validator_balance > 0:
                    validator_unstake = min(validator_balance, remaining_unstake)
                    
                    if validator_unstake > 0:
                        print(f"🔄 Unstaking {validator_unstake:.6f} α from validator hotkey {validator_hotkey[:5]}...")
                        
                        try:
                            results = await sub.unstake(
                                wallet=wallet,
                                hotkey_ss58=validator_hotkey,
                                netuid=netuid,
                                amount=bt.Balance.from_float(validator_unstake),
                            )
                            
                            if not results:
                                print(f"⚠️ Failed to unstake from validator hotkey {validator_hotkey[:5]}...")
                            else:
                                total_unstaked += validator_unstake
                                remaining_unstake -= validator_unstake
                                print(f"✅ Successfully unstaked {validator_unstake:.6f} α from validator hotkey {validator_hotkey[:5]}...")
                        except Exception as e:
                            print(f"⚠️ Error unstaking from validator hotkey {validator_hotkey[:5]}...: {e}")
            
            # Unstake from regular hotkey if needed
            if remaining_unstake > 0:
                regular_unstake = min(regular_hotkey_balance, remaining_unstake)
                
                if regular_unstake > 0:
                    print(f"🔄 Unstaking {regular_unstake:.6f} α from regular hotkey {wallet.hotkey.ss58_address[:5]}...")
                    
                    try:
                        results = await sub.unstake(
                            wallet=wallet,
                            netuid=netuid,
                            amount=bt.Balance.from_float(regular_unstake),
                        )
                        
                        if not results:
                            print(f"⚠️ Failed to unstake from regular hotkey")
                        else:
                            total_unstaked += regular_unstake
                            print(f"✅ Successfully unstaked {regular_unstake:.6f} α from regular hotkey")
                    except Exception as e:
                        print(f"⚠️ Error unstaking from regular hotkey: {e}")
            
            # Calculate the proportion of requested amount that was actually unstaked
            proportion_unstaked = total_unstaked / alpha_amount if alpha_amount > 0 else 0
            
            # Adjust the expected tao impact proportionally
            adjusted_tao_impact = total_tao_impact * proportion_unstaked
            
            # Get slippage from subnet info for logging
            subnet_info = await sub.subnet(netuid)
            tao_conversion = subnet_info.alpha_to_tao_with_slippage(alpha=total_unstaked)
            slippage = float(tao_conversion[1].tao)
            
            print(f"✅ Successfully unstaked total of {total_unstaked:.6f} α ≈ {adjusted_tao_impact:.6f} τ @ {alpha_price:.6f}")
            
            # Log the operation with the adjusted values
            log_operation(
                db=db,
                wallet=wallet,
                operation='unstake',
                amount_tao=adjusted_tao_impact,
                amount_alpha=total_unstaked,
                price_tao=alpha_price,
                ema_price=moving_price,
                slippage=slippage,
                success=True,
                test_mode=test_mode
            )
            return True
        else:
            print(f"🧪 TEST MODE: Would have unstaked:")
            print(f"  • From validator hotkeys: {min(total_validator_balance, alpha_amount):.6f} α")
            if alpha_amount > total_validator_balance:
                print(f"  • From regular hotkey: {min(regular_hotkey_balance, alpha_amount - total_validator_balance):.6f} α")
            print(f"  • Total: {min(regular_hotkey_balance + total_validator_balance, alpha_amount):.6f} α ≈ {total_tao_impact:.6f} τ")
            return True
    except Exception as e:
        log_operation(
            db=db,
            wallet=wallet,
            operation='unstake',
            amount_tao=total_tao_impact,
            amount_alpha=alpha_amount,
            price_tao=alpha_price,
            ema_price=moving_price,
            slippage=slippage if 'slippage' in locals() else 0.0,
            success=False,
            error_msg=str(e),
            test_mode=test_mode
        )
        print(f"❌ Error during unstake: {e}")
        return False
    
async def chase_ema(netuid, wallet):
    """Run one cycle of EMA chasing for a wallet"""
    remaining_budget = args.budget  # Initialize remaining budget
    subnet_info_displayed = False
    
    try:
        async with bt.AsyncSubtensor(SUBTENSOR) as sub:

            while True:
                try:
                    # Add retry logic and better error handling
                    max_attempts = 3
                    retry_delay = 5  # seconds
                    subnet_info = None
                    
                    for attempt in range(1, max_attempts + 1):
                        try:
                            subnet_info = await sub.subnet(netuid)
                            # Verify subnet_info is not None and has expected attributes
                            if subnet_info is None:
                                print(f"⚠️ Attempt {attempt}/{max_attempts}: subnet_info is None, retrying...")
                                await asyncio.sleep(retry_delay)
                                continue
                                
                            # Try accessing essential attributes to ensure subnet_info is valid
                            try:
                                # Try accessing essential attributes to ensure subnet_info is valid
                                alpha_price = float(subnet_info.price.tao)
                                moving_price = float(subnet_info.moving_price) * 1e11
                                break
                            except AttributeError as attr_error:
                                # Handle the case where the standard access method fails
                                try:
                                    # Some versions of bittensor might store this differently
                                    if "price" in str(attr_error):
                                        alpha_price = float(subnet_info.price)
                                        print("⚠️ Using fallback price access method")
                                    
                                    if "moving_price" in str(attr_error):
                                        # Try a different way to access moving_price
                                        moving_price = float(subnet_info.ema_price) * 1e11 if hasattr(subnet_info, 'ema_price') else 0.0
                                        print("⚠️ Using fallback moving_price access method")
                                    
                                    # Only break if we successfully set both prices
                                    if 'alpha_price' in locals() and 'moving_price' in locals():
                                        break
                                    else:
                                        raise Exception("Could not access all required price information")
                                except (AttributeError, TypeError):
                                    # If fallback also fails, continue to next attempt
                                    print(f"⚠️ Both standard and fallback price access methods failed")
                                    continue
                            
                        except Exception as e:
                            print(f"⚠️ Attempt {attempt}/{max_attempts}: Error getting subnet info: {str(e)}")
                            if attempt < max_attempts:
                                print(f"Retrying in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                            else:
                                print("❌ Max attempts reached. Unable to get valid subnet info.")
                                raise  # Re-raise to be caught by outer try/except
                    
                    # Safety check before proceeding
                    if subnet_info is None:
                        print("❌ Failed to get valid subnet info after all attempts.")
                        raise Exception("Failed to get valid subnet info")
                    
                    # Get current balances with error handling
                    try:
                        current_stake = await sub.get_stake(
                            coldkey_ss58 = wallet.coldkeypub.ss58_address,
                            hotkey_ss58 = wallet.hotkey.ss58_address,
                            netuid = netuid,
                        )
                    except Exception as e:
                        print(f"❌ Error getting stake: {e}")
                        break
                        
                    try:
                        balance = await sub.get_balance(wallet.coldkeypub.ss58_address)
                    except Exception as e:
                        print(f"❌ Error getting balance: {e}")
                        break

                    # Calculate what percentage the current price is of the EMA
                    price_diff_pct = (alpha_price / moving_price) - 1.0

                    # Skip if price difference is less than minimum required
                    if abs(price_diff_pct) < args.min_price_diff:
                        print(f"\n⏳ Price difference ({price_diff_pct:.2%}) < minimum required ({args.min_price_diff:.2%})")
                        print("💤 Waiting for larger price movement...")
                        await sub.wait_for_block()
                        break

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
                                ('Moving Price (Tao)', f"{float(moving_price):.5f}"),
                                ('Price Difference', f"{((alpha_price - moving_price) / moving_price):.2%}")
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

                    # Check if balance is too low - only for staking scenario (when alpha price < EMA)
                    if alpha_price < moving_price and float(balance) < DCA_RESERVE_TAO:
                        print(f"\n⚠️  Balance ({float(balance):.6f} τ) below TAO reserve minimum ({DCA_RESERVE_TAO} τ)")
                        print(f"    Can't stake when below minimum TAO reserve.")
                        break

                    # Calculate dynamic slippage if enabled
                    target_slippage = args.slippage
                    if args.dynamic_slippage:
                        # Get the maximum price difference, default to 20% if not specified
                        max_price_diff = args.max_price_diff if args.max_price_diff is not None else 0.20
                        
                        # Calculate scale factor based on how close we are to min_price_diff
                        # 1.0 = full slippage when far from EMA
                        # 0.0 = no slippage when at min_price_diff
                        scale_factor = min(1.0, max(0.0, 
                            abs(price_diff_pct) - args.min_price_diff) / 
                            (max_price_diff - args.min_price_diff) if max_price_diff > args.min_price_diff else 0.0
                        )
                        
                        # Scale slippage down from base slippage as we get closer to EMA
                        target_slippage = args.slippage * scale_factor
                        
                        print(f"\n📊 Dynamic Slippage Adjustment")
                        print("-" * 40)
                        print(f"{'Base Slippage':20}: {args.slippage:.6f}")
                        print(f"{'Min Price Diff':20}: {args.min_price_diff:.2%}")
                        print(f"{'Max Price Diff':20}: {max_price_diff:.2%}")
                        print(f"{'Current Price Diff':20}: {price_diff_pct:.2%}")
                        print(f"{'Scale Factor':20}: {scale_factor:.2f}")
                        print(f"{'Target Slippage':20}: {target_slippage:.6f}")
                        print("-" * 40)

                    # Set max_increment based on budget or available balance
                    if args.budget == 0:
                        if alpha_price > moving_price:  # Unstaking
                            # Calculate available alpha considering reserve
                            available_alpha = float(current_stake) - DCA_RESERVE_ALPHA
                            if available_alpha <= 0:
                                print(f"\n⚠️  Current stake ({float(current_stake):.6f} α) is less than or equal to alpha reserve ({DCA_RESERVE_ALPHA} α)")
                                break
                                
                            # Convert available alpha to TAO to get maximum available
                            stake_conversion = subnet_info.alpha_to_tao_with_slippage(alpha=available_alpha)
                            max_increment = float(stake_conversion[0].tao + stake_conversion[1].tao)
                        else:  # Staking
                            # Account for TAO reserve when staking
                            max_increment = float(balance) - DCA_RESERVE_TAO
                    else:
                        max_increment = remaining_budget

                    if max_increment <= 0:
                        if args.budget > 0:
                            print(f"\n✨ Budget exhausted. Total used: {args.budget - remaining_budget:.6f} TAO")
                        else:
                            print(f"\n✨ Available balance/stake exhausted")
                        break

                    # Rest of the binary search code remains the same
                    min_increment = 0.0
                    best_increment = 0.0
                    closest_slippage = float('inf')
                    iterations = []
                    
                    print("\n🔍 Finding optimal trade size...")
                    while (max_increment - min_increment) > 1e-12:  # Even more precision
                        current_increment = (min_increment + max_increment) / 2
                        slippage_tuple = subnet_info.slippage(current_increment)
                        slippage = float(slippage_tuple[1].tao)
                        
                        # Store iteration info
                        iterations.append((current_increment, slippage))
                        
                        if abs(slippage - target_slippage) < abs(closest_slippage - target_slippage):
                            closest_slippage = slippage
                            best_increment = current_increment
                        
                        if abs(slippage - target_slippage) < 1e-12:  # Matching precision
                            break
                        elif slippage < target_slippage:
                            min_increment = current_increment
                        else:
                            max_increment = current_increment

                    # Print first 3 and last 3 iterations
                    for i, (inc, slip) in enumerate(iterations):
                        if i < 3 or i >= len(iterations) - 3:
                            print(f"  • Testing {inc:.12f} TAO → {slip:.12f} slippage")
                        elif i == 3:
                            print("  • ...")

                    increment = best_increment
                    print(f"\n💫 Trade Parameters")
                    print("-" * 40)
                    print(f"{'Size':20}: {increment:.12f} TAO")
                    print(f"{'Slippage':20}: {float(subnet_info.slippage(increment)[1].tao):.12f} TAO")
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
                            break
                            
                        print(f"\n📉 Price above EMA - UNSTAKING cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")
                        
                        # Convert alpha amount to TAO equivalent including slippage
                        alpha_amount = increment / alpha_price
                        
                        # Check if unstaking would leave less than DCA_RESERVE_ALPHA
                        available_alpha = float(current_stake) - DCA_RESERVE_ALPHA
                        if available_alpha <= 0:
                            print(f"\n⚠️  Current stake ({float(current_stake):.6f} α) is less than or equal to alpha reserve ({DCA_RESERVE_ALPHA} α)")
                            break
                            
                        # Adjust alpha_amount if it would leave less than DCA_RESERVE_ALPHA
                        if alpha_amount > available_alpha:
                            print(f"\n⚠️  Reducing unstake amount from {alpha_amount:.6f} α to {available_alpha:.6f} α to maintain alpha reserve")
                            alpha_amount = available_alpha
                            
                        tao_conversion = subnet_info.alpha_to_tao_with_slippage(alpha=alpha_amount)
                        total_tao_impact = float(tao_conversion[0].tao + tao_conversion[1].tao)
                        
                        if args.budget > 0 and total_tao_impact > remaining_budget:
                            print(f"❌ Unstaking {alpha_amount} α would result in {total_tao_impact} τ impact, exceeding budget of {remaining_budget} τ")
                            break

                        success = await perform_unstake(
                            sub=sub,
                            wallet=wallet,
                            netuid=netuid,
                            alpha_amount=alpha_amount,
                            total_tao_impact=total_tao_impact,
                            alpha_price=alpha_price,
                            moving_price=moving_price,
                            test_mode=TEST_MODE
                        )
                        
                        if success and args.budget > 0:
                            remaining_budget -= total_tao_impact
                            await asyncio.sleep(1)

                    elif alpha_price < moving_price:
                        if args.one_way_mode == 'unstake':
                            print("⏭️  Price below EMA but unstake-only mode active. Skipping...")
                            await sub.wait_for_block()
                            break
                            
                        print(f"\n📈 Price below EMA - STAKING cold({wallet.coldkeypub.ss58_address[:5]}...) hot({wallet.hotkey.ss58_address[:5]}...)")

                        if args.budget > 0 and increment > remaining_budget:
                            print("❌ Insufficient remaining budget")
                            break

                        success = await perform_stake(
                            sub=sub,
                            wallet=wallet,
                            netuid=netuid,
                            increment=increment,
                            alpha_price=alpha_price,
                            moving_price=moving_price,
                            subnet_info=subnet_info,
                            test_mode=TEST_MODE
                        )
                        
                        if success and args.budget > 0:
                            remaining_budget -= increment
                            await asyncio.sleep(1)

                    else:
                        print("🦄 Price equals EMA - No action needed")
                        await sub.wait_for_block()
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
                        reports.print_summary(hours_segments=[24])
                        #reports.print_wallet_summary(wallet.coldkeypub.ss58_address)
                        print("\n⏭️ Moving to next wallet...")
                        await sub.wait_for_block()
                        break
                    
                    # For single wallet mode, continue to next block
                    print("\n⏳ Waiting for next block...")
                    await sub.wait_for_block()

                except Exception as e:
                    print(f"❌ Error in main loop: {e}")
                    print("⏳ Waiting before retry...")
                    await asyncio.sleep(BLOCK_TIME_SECONDS)
                    break
                    
    except Exception as e:
        print(f"❌ Error connecting to Subtensor: {e}")
        print("⚠️ Make sure Subtensor endpoint is accessible")
        if SUBTENSOR == 'finney':
            print("💡 Try using ws://127.0.0.1:9944 with a local node instead")

async def main(wallets=None, single_wallet=None):
    """Main execution function.
    
    Args:
        wallets: List of unlocked wallet objects for rotation
        single_wallet: Single wallet object for specific operations
    """
    # Apply CLI overrides for reserve values if provided
    global DCA_RESERVE_ALPHA, DCA_RESERVE_TAO
    if args.alpha_reserve is not None:
        DCA_RESERVE_ALPHA = args.alpha_reserve
        print(f"🔄 Using CLI override for alpha reserve: {DCA_RESERVE_ALPHA}")
    
    if args.tao_reserve is not None:
        DCA_RESERVE_TAO = args.tao_reserve
        print(f"🔄 Using CLI override for TAO reserve: {DCA_RESERVE_TAO}")
        
    if args.harvest_alpha:
        # All wallets mode or single wallet with all hotkeys mode
        if wallets:
            print(f"\n🔄 Starting alpha harvesting for {'all wallets' if args.rotate_all_wallets else f'all hotkeys of wallet: {args.wallet}'}")
            while True:
                await rotate_wallets_for_harvest(args.netuid, wallets)
        else:
            print("❌ No wallets were initialized")
            sys.exit(1)
    else:
        # Original EMA chasing mode
        if args.rotate_all_wallets:
            # Initialize all wallets first
            unlocked_wallets = initialize_wallets(bt)
            while True:
                await rotate_wallets(args.netuid, unlocked_wallets)
        else:
            # Original single wallet mode
            while True:
                await chase_ema(args.netuid, wallet)

async def harvest_alpha_for_tao_reserve(sub, wallet, netuid, target_slippage, test_mode=False):
    """Harvest excess alpha to maintain TAO reserve and replenish up to DCA_RESERVE_TAO amount.
    
    This function:
    1. Checks current TAO balance
    2. If below DCA_RESERVE_TAO, calculates how much alpha to unstake
    3. Performs unstaking in increments that maintain slippage target
    
    Returns:
        tuple: (success, remaining_deficit, has_more_alpha)
            - success: Whether the operation was successful
            - remaining_deficit: How much more TAO is needed to reach DCA_RESERVE_TAO
            - has_more_alpha: Whether there's still alpha available to unstake
    """
    try:
        # Get wallet information
        coldkey_ss58 = wallet.coldkeypub.ss58_address
        hotkey_ss58 = wallet.hotkey.ss58_address
        cold_addr = coldkey_ss58[:5] + "..."
        hot_addr = hotkey_ss58[:5] + "..."
        
        print(f"\n🔄 Alpha harvesting for wallet: cold({cold_addr}) hot({hot_addr})")
        
        # Get subnet info for price information
        # Add retry logic and better error handling
        max_attempts = 3
        retry_delay = 5  # seconds
        subnet_info = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Add specific handling for MetadataVersioned errors
                try:
                    subnet_info = await sub.subnet(netuid)
                except Exception as e:
                    if "MetadataVersioned" in str(e) and "decoded" in str(e):
                        print(f"⚠️ Caught Bittensor API metadata error: {e}")
                        print(f"⏳ Waiting before retry...")
                        await asyncio.sleep(retry_delay * 2)  # Wait longer for API-related issues
                        raise  # Re-raise to trigger the outer retry logic
                    else:
                        raise  # Re-raise other exceptions
                
                # Verify subnet_info is not None and has expected attributes
                if subnet_info is None:
                    print(f"⚠️ Attempt {attempt}/{max_attempts}: subnet_info is None, retrying...")
                    await asyncio.sleep(retry_delay)
                    continue
                    
                # Try accessing essential attributes to ensure subnet_info is valid
                try:
                    # Try accessing essential attributes to ensure subnet_info is valid
                    alpha_price = float(subnet_info.price.tao)
                    moving_price = float(subnet_info.moving_price) * 1e11
                    break
                except AttributeError as attr_error:
                    # Handle the case where the standard access method fails
                    try:
                        # Some versions of bittensor might store this differently
                        if "price" in str(attr_error):
                            alpha_price = float(subnet_info.price)
                            print("⚠️ Using fallback price access method")
                        
                        if "moving_price" in str(attr_error):
                            # Try a different way to access moving_price
                            moving_price = float(subnet_info.ema_price) * 1e11 if hasattr(subnet_info, 'ema_price') else 0.0
                            print("⚠️ Using fallback moving_price access method")
                        
                        # Only break if we successfully set both prices
                        if 'alpha_price' in locals() and 'moving_price' in locals():
                            break
                        else:
                            raise Exception("Could not access all required price information")
                    except (AttributeError, TypeError):
                        # If fallback also fails, continue to next attempt
                        print(f"⚠️ Both standard and fallback price access methods failed")
                        continue
                
            except Exception as e:
                print(f"⚠️ Attempt {attempt}/{max_attempts}: Error getting subnet info: {str(e)}")
                if attempt < max_attempts:
                    print(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    print("❌ Max attempts reached. Unable to get valid subnet info.")
                    return False, 0, False  # Exit gracefully
        
        # Safety check before proceeding
        if subnet_info is None:
            print("❌ Failed to get valid subnet info after all attempts.")
            return False, 0, False  # Exit the function gracefully
        
        # Get current balances
        try:
            # Add specific error handling for stake fetching
            try:
                # Get stake balance (alpha)
                current_stake = await sub.get_stake(
                    coldkey_ss58=coldkey_ss58,
                    hotkey_ss58=hotkey_ss58,
                    netuid=netuid,
                )
                alpha_balance = float(current_stake)
            except Exception as e:
                if "MetadataVersioned" in str(e) and "decoded" in str(e):
                    print(f"⚠️ Error with metadata while getting stake: {e}")
                    print(f"⏳ Waiting before retry...")
                    await asyncio.sleep(retry_delay)
                    return False, 0, False  # Exit gracefully to allow outer retry
                elif "NoneType" in str(e) and "offset" in str(e):
                    print(f"⚠️ Error with offset while getting stake: {e}")
                    print(f"⏳ Waiting before retry...")
                    await asyncio.sleep(retry_delay)
                    return False, 0, False  # Exit gracefully to allow outer retry
                else:
                    print(f"❌ Error getting stake: {e}")
                    return False, 0, False

            # Get stake balance on validator hotkeys
            total_validator_alpha = 0.0
            
            for validator_hotkey in VALIDATOR_HOTKEYS:
                try:
                    validator_stake = await sub.get_stake(
                        coldkey_ss58=coldkey_ss58,
                        hotkey_ss58=validator_hotkey,
                        netuid=netuid,
                    )
                    validator_alpha_balance = float(validator_stake)
                    total_validator_alpha += validator_alpha_balance
                    print(f"💰 {wallet.name} α on validator {validator_hotkey[:5]}...: {validator_alpha_balance:.6f} α")
                except Exception as e:
                    if "MetadataVersioned" in str(e) and "decoded" in str(e):
                        print(f"⚠️ Metadata error with validator {validator_hotkey[:5]}...: {e}")
                    elif "NoneType" in str(e) and "offset" in str(e):
                        print(f"⚠️ Offset error with validator {validator_hotkey[:5]}...: {e}")
                    else:
                        print(f"⚠️ Error getting {wallet.name} stake on validator {validator_hotkey[:5]}...: {e}")
            
            print(f"💰 {wallet.name} total validator α: {total_validator_alpha:.6f} α")
            alpha_balance += total_validator_alpha
            
            # Get TAO balance with metadata error handling
            try:
                balance = await sub.get_balance(coldkey_ss58)
                tao_balance = float(balance)
            except Exception as e:
                if "MetadataVersioned" in str(e) and "decoded" in str(e):
                    print(f"⚠️ Metadata error while getting balance: {e}")
                    print(f"⏳ Waiting before retry...")
                    await asyncio.sleep(retry_delay)
                    return False, 0, False  # Exit gracefully to allow outer retry
                elif "NoneType" in str(e) and "offset" in str(e):
                    print(f"⚠️ Offset error while getting balance: {e}")
                    print(f"⏳ Waiting before retry...")
                    await asyncio.sleep(retry_delay)
                    return False, 0, False  # Exit gracefully to allow outer retry
                else:
                    print(f"❌ Error getting balance: {e}")
                    return False, 0, False
        except Exception as e:
            print(f"❌ Error retrieving balances: {e}")
            return False, 0, False
        
        # Show current balances
        print(f"   Current τ balance: {tao_balance:.6f} τ")
        print(f"   Current α balance: {alpha_balance:.6f} α")
        print(f"   τ reserve target: {DCA_RESERVE_TAO:.6f} τ")
        print(f"   α reserve minimum: {DCA_RESERVE_ALPHA:.6f} α")
        print(f"   Current α price: {alpha_price:.6f} τ")
        
        # Check if TAO balance is already sufficient
        if tao_balance >= DCA_RESERVE_TAO:
            print(f"   ✅ TAO balance ({tao_balance:.6f} τ) is already above reserve target ({DCA_RESERVE_TAO:.6f} τ)")
            return True, 0, True
        
        # Calculate how much TAO we need
        tao_deficit = DCA_RESERVE_TAO - tao_balance
        print(f"   TAO deficit: {tao_deficit:.6f} τ")
        
        # Check if we have enough alpha to unstake while maintaining minimum reserve
        available_alpha = alpha_balance - DCA_RESERVE_ALPHA
        if available_alpha <= 0:
            print(f"   ⚠️ No excess α available for harvesting (current: {alpha_balance:.6f} α, minimum: {DCA_RESERVE_ALPHA:.6f} α)")
            return False, tao_deficit, False
        
        # Calculate alpha needed to cover the deficit
        # This is a rough estimate, as slippage will affect the final amount
        alpha_needed_estimate = tao_deficit / alpha_price
        
        # Limit to available alpha
        alpha_to_unstake = min(alpha_needed_estimate, available_alpha)
        print(f"   Estimated α needed: {alpha_needed_estimate:.6f} α")
        print(f"   Available α for unstaking: {available_alpha:.6f} α")
        print(f"   Will attempt to unstake: {alpha_to_unstake:.6f} α")
        
        # Determine optimal unstaking amount that respects slippage target
        # We'll use binary search to find the right amount of alpha to unstake
        print(f"\n🔍 Finding optimal unstake amount with target slippage {target_slippage:.6f} τ...")
        
        min_alpha = 0.0
        max_alpha = alpha_to_unstake
        best_alpha = 0.0
        closest_slippage = float('inf')
        iterations = []
        
        while (max_alpha - min_alpha) > 1e-12:
            current_alpha = (min_alpha + max_alpha) / 2
            
            # Get expected slippage for this alpha amount
            tao_conversion = subnet_info.alpha_to_tao_with_slippage(alpha=current_alpha)
            slippage = float(tao_conversion[1].tao)
            expected_tao = float(tao_conversion[0].tao)
            
            # Store iteration info
            iterations.append((current_alpha, slippage, expected_tao))
            
            if abs(slippage - target_slippage) < abs(closest_slippage - target_slippage):
                closest_slippage = slippage
                best_alpha = current_alpha
            
            if abs(slippage - target_slippage) < 1e-12:  # Matching precision
                break
            elif slippage < target_slippage:
                min_alpha = current_alpha
            else:
                max_alpha = current_alpha
        
        # Print first 3 and last 3 iterations
        for i, (alpha, slip, tao) in enumerate(iterations):
            if i < 3 or i >= len(iterations) - 3:
                print(f"  • Testing {alpha:.6f} α → {slip:.6f} τ slippage, {tao:.6f} τ expected")
            elif i == 3:
                print("  • ...")
        
        # Use the best alpha amount found
        alpha_amount = best_alpha
        tao_conversion = subnet_info.alpha_to_tao_with_slippage(alpha=alpha_amount)
        total_tao_impact = float(tao_conversion[0].tao + tao_conversion[1].tao)
        
        print(f"\n💫 Unstake Parameters")
        print("-" * 40)
        print(f"{'Amount to unstake':25}: {alpha_amount:.6f} α")
        print(f"{'Expected TAO received':25}: {total_tao_impact:.6f} τ")
        print(f"{'Slippage':25}: {float(tao_conversion[1].tao):.6f} τ")
        print(f"{'New TAO balance (est)':25}: {(tao_balance + total_tao_impact):.6f} τ")
        print(f"{'New alpha balance (est)':25}: {(alpha_balance - alpha_amount):.6f} α")
        
        # Check if amount is below minimum unstake threshold
        if alpha_amount < MIN_UNSTAKE_ALPHA:
            print(f"   ⚠️ Calculated unstake amount ({alpha_amount:.6f} α) is below minimum threshold ({MIN_UNSTAKE_ALPHA:.6f} α)")
            print(f"   ⏭️ Skipping unstake operation to avoid transaction errors")
            
            # If the TAO deficit is very small, consider it "good enough" to avoid endless retries
            if tao_deficit < MIN_TAO_DEFICIT:  # If we're close enough to the target
                print(f"   ✓ TAO deficit ({tao_deficit:.6f} τ) is below minimum threshold ({MIN_TAO_DEFICIT:.6f} τ), considering target achieved")
                return True, 0, False  # Mark as success with no deficit to prevent further attempts
            
            return False, tao_deficit, (available_alpha > 0)
        
        # Perform the unstake
        success = await perform_unstake(
            sub=sub,
            wallet=wallet,
            netuid=netuid,
            alpha_amount=alpha_amount,
            total_tao_impact=total_tao_impact,
            alpha_price=alpha_price,
            moving_price=moving_price,
            test_mode=test_mode
        )
        
        if success:
            # Calculate new balances and remaining deficit
            new_tao_balance = tao_balance + total_tao_impact
            new_alpha_balance = alpha_balance - alpha_amount
            remaining_deficit = max(0, DCA_RESERVE_TAO - new_tao_balance)
            has_more_alpha = (new_alpha_balance - DCA_RESERVE_ALPHA) > 0
            
            # Report on the results
            if remaining_deficit > 0:
                print(f"\n🔷 Harvested {alpha_amount:.6f} α for {total_tao_impact:.6f} τ")
                print(f"   Still need {remaining_deficit:.6f} τ to reach target")
                if has_more_alpha:
                    print(f"   This wallet has more α available for harvesting in next rotation")
            else:
                print(f"\n✅ Successfully harvested {alpha_amount:.6f} α for {total_tao_impact:.6f} τ")
                print(f"   Target TAO reserve of {DCA_RESERVE_TAO:.6f} τ reached or exceeded")
            
            return True, remaining_deficit, has_more_alpha
        else:
            print(f"❌ Failed to unstake alpha")
            return False, tao_deficit, (available_alpha > 0)
    except Exception as e:
        print(f"❌ Error during alpha harvesting: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, False

async def rotate_wallets_for_harvest(netuid, unlocked_wallets):
    """Rotate through all wallets and harvest alpha to maintain TAO reserve.
    
    This function:
    1. Fetches balances for all wallets upfront
    2. Filters wallets that need TAO replenishment
    3. Sorts wallets by available alpha (highest first)
    4. Processes wallets in optimal order
    
    Note: Unlike the EMA chasing mode, alpha harvesting mode processes ALL wallets,
    including the holding wallet, since we want to maintain TAO reserves in all wallets.
    """
    # Include all wallets (including the holding wallet) for alpha harvesting
    wallets = unlocked_wallets
    
    print(f"\n🔄 Starting alpha harvesting rotation for {len(wallets)} wallets...")
    print(f"📊 Target: Maintain at least {DCA_RESERVE_TAO} τ and {DCA_RESERVE_ALPHA} α in each wallet")
    print("=" * 60)
    
    # Track wallets that need another pass
    wallets_needing_more_tao = []
    
    try:
        # Fetch all wallet balances upfront
        wallet_data = []
        
        print("\n📊 Pre-fetching wallet balances...")
        
        # Set up a retry mechanism for the entire operation
        max_rotation_attempts = 3
        for rotation_attempt in range(1, max_rotation_attempts + 1):
            try:
                async with bt.AsyncSubtensor(SUBTENSOR) as sub:
                    # Get subnet info for price information
                    # Add retry logic and better error handling
                    max_attempts = 3
                    retry_delay = 5  # seconds
                    subnet_info = None
                    
                    for attempt in range(1, max_attempts + 1):
                        try:
                            subnet_info = await sub.subnet(netuid)
                            # Verify subnet_info is not None and has expected attributes
                            if subnet_info is None:
                                print(f"⚠️ Attempt {attempt}/{max_attempts}: subnet_info is None, retrying...")
                                await asyncio.sleep(retry_delay)
                                continue
                            
                            # Use a more robust way to access the price
                            try:
                                # Try accessing essential attributes to ensure subnet_info is valid
                                alpha_price = float(subnet_info.price.tao)
                                break
                            except AttributeError:
                                # If the standard access method fails, try the fallback approach
                                try:
                                    # Some versions of bittensor might store this differently
                                    alpha_price = float(subnet_info.price)
                                    print("⚠️ Using fallback price access method")
                                    break
                                except (AttributeError, TypeError):
                                    raise Exception("Could not access price information")
                            
                        except Exception as e:
                            print(f"⚠️ Attempt {attempt}/{max_attempts}: Error getting subnet info: {str(e)}")
                            if attempt < max_attempts:
                                print(f"Retrying in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                            else:
                                print("❌ Max attempts reached. Unable to get valid subnet info.")
                                raise  # Re-raise to be caught by outer try/except
                    
                    # Safety check before proceeding
                    if subnet_info is None:
                        print("❌ Failed to get valid subnet info after all attempts.")
                        raise Exception("Failed to get valid subnet info")
                    
                    for wallet in wallets:
                        try:
                            # Wrap each balance fetch in its own try-except
                            try:
                                # Get stake balance (alpha)
                                current_stake = await sub.get_stake(
                                    coldkey_ss58=wallet.coldkeypub.ss58_address,
                                    hotkey_ss58=wallet.hotkey.ss58_address,
                                    netuid=netuid,
                                )
                                alpha_balance = float(current_stake)
                                print(f"💰 {wallet.name} has {alpha_balance:.6f} α")
                            except Exception as e:
                                print(f"⚠️ Error getting stake for {wallet.name}: {e}")
                                alpha_balance = 0.0

                            # Get stake balance on validator hotkeys
                            total_validator_alpha = 0.0
                            
                            for validator_hotkey in VALIDATOR_HOTKEYS:
                                try:
                                    validator_stake = await sub.get_stake(
                                        coldkey_ss58=wallet.coldkeypub.ss58_address,
                                        hotkey_ss58=validator_hotkey,
                                        netuid=netuid,
                                    )
                                    validator_alpha_balance = float(validator_stake)
                                    total_validator_alpha += validator_alpha_balance
                                    print(f"💰 {wallet.name} α on validator {validator_hotkey[:5]}...: {validator_alpha_balance:.6f} α")
                                except Exception as e:
                                    print(f"⚠️ Error getting {wallet.name} stake on validator {validator_hotkey[:5]}...: {e}")
                            
                            print(f"💰 {wallet.name} total validator α: {total_validator_alpha:.6f} α")
                            alpha_balance += total_validator_alpha
                            
                            # Calculate available alpha (excess above reserve)
                            available_alpha = max(0, alpha_balance - DCA_RESERVE_ALPHA)
                            
                            try:
                                # Get TAO balance
                                balance = await sub.get_balance(wallet.coldkeypub.ss58_address)
                                tao_balance = float(balance)
                                print(f"💰 {wallet.name} has {tao_balance:.6f} τ")
                            except Exception as e:
                                print(f"⚠️ Error getting balance for {wallet.name}: {e}")
                                tao_balance = 0.0
                                
                            # Calculate TAO deficit
                            tao_deficit = max(0, DCA_RESERVE_TAO - tao_balance)
                            
                            # Add wallet data
                            cold_addr = wallet.coldkeypub.ss58_address[:5] + "..."
                            hot_addr = wallet.hotkey.ss58_address[:5] + "..."
                            
                            # Add a flag to identify the holding wallet
                            is_holding = wallet.name == HOLDING_WALLET_NAME
                            
                            wallet_data.append({
                                'wallet': wallet,
                                'name': wallet.name + (" (Holding)" if is_holding else ""),
                                'addresses': f"cold({cold_addr}) hot({hot_addr})",
                                'alpha_balance': alpha_balance,
                                'tao_balance': tao_balance,
                                'available_alpha': available_alpha,
                                'tao_deficit': tao_deficit,
                                'potential_tao': available_alpha * alpha_price,  # Rough estimate of potential TAO
                                'is_holding': is_holding
                            })
                            
                        except Exception as e:
                            print(f"❌ Error fetching balances for wallet {wallet.name}: {e}")
                    
                # If we get here, we successfully retrieved all wallet data
                break
                
            except Exception as e:
                if "MetadataVersioned" in str(e) or "decoded" in str(e):
                    print(f"⚠️ Rotation attempt {rotation_attempt}/{max_rotation_attempts}: Bittensor API error: {e}")
                    if rotation_attempt < max_rotation_attempts:
                        print(f"This appears to be an issue with the Bittensor API. Retrying in 10 seconds...")
                        await asyncio.sleep(10)
                    else:
                        print("❌ Max rotation attempts reached. Unable to proceed.")
                        raise
                elif "NoneType" in str(e) and "offset" in str(e):
                    print(f"⚠️ Rotation attempt {rotation_attempt}/{max_rotation_attempts}: NoneType offset error: {e}")
                    if rotation_attempt < max_rotation_attempts:
                        print(f"This appears to be an issue with the Bittensor chain data. Retrying in 15 seconds...")
                        await asyncio.sleep(15)  # Wait a bit longer for these errors
                    else:
                        print("❌ Max rotation attempts reached. Unable to proceed.")
                        raise
                else:
                    print(f"❌ Unexpected error in wallet rotation: {e}")
                    raise

        # If we have no wallet data after all retries, exit gracefully
        if not wallet_data:
            print("❌ No wallet data could be retrieved after all attempts.")
            return
        
        # Filter wallets that need TAO
        needy_wallets = [w for w in wallet_data if w['tao_deficit'] > 0]
        
        # Sort by available alpha (highest first)
        needy_wallets.sort(key=lambda w: w['available_alpha'], reverse=True)
        
        print(f"\n📝 Found {len(needy_wallets)} of {len(wallets)} wallets below TAO reserve")
        
        # Print summary of wallets sorted by available alpha
        if needy_wallets:
            print("\n🔄 Wallets to process (sorted by available alpha):")
            print("-" * 85)
            print(f"{'#':3} {'Wallet':20} {'Addresses':25} {'α Balance':12} {'τ Balance':12} {'τ Deficit':12}")
            print("-" * 85)
            
            for i, w in enumerate(needy_wallets):
                print(f"{i+1:3} {w['name']:20} {w['addresses']:25} {w['alpha_balance']:12.6f} {w['tao_balance']:12.6f} {w['tao_deficit']:12.6f}")
            
            print("-" * 85)
        else:
            print("✅ All wallets have sufficient TAO reserves")
            return
        
        # Process wallets that need TAO in order of available alpha
        async with bt.AsyncSubtensor(SUBTENSOR) as sub:
            for i, wallet_info in enumerate(needy_wallets):
                wallet = wallet_info['wallet']
                
                print(f"\n[{i+1}/{len(needy_wallets)}] 🔄 Processing wallet: {wallet_info['name']}")
                print(f"   Current α: {wallet_info['alpha_balance']:.6f}, τ: {wallet_info['tao_balance']:.6f}, Deficit: {wallet_info['tao_deficit']:.6f} τ")
                
                # Skip wallets with no available alpha
                if wallet_info['available_alpha'] <= 0:
                    print(f"   ⏭️ Skipping wallet with no available alpha")
                    continue
                
                success, remaining_deficit, has_more_alpha = await harvest_alpha_for_tao_reserve(
                    sub=sub, 
                    wallet=wallet, 
                    netuid=netuid, 
                    target_slippage=args.slippage, 
                    test_mode=TEST_MODE
                )
                
                # If the wallet still needs TAO and has more alpha to unstake,
                # add it to the list for another pass
                if success and remaining_deficit > 0 and has_more_alpha:
                    print(f"   📝 Adding wallet {wallet_info['name']} to queue for another pass (deficit: {remaining_deficit:.6f} τ)")
                    wallets_needing_more_tao.append(wallet)
                
                print("⏳ Waiting before next wallet...")
                await sub.wait_for_block()
            
            # If we have wallets needing another pass, process them
            if wallets_needing_more_tao:
                print(f"\n🔄 Starting second pass for {len(wallets_needing_more_tao)} wallets that need more TAO...")
                
                for i, wallet in enumerate(wallets_needing_more_tao):
                    wallet_name = wallet.name
                    if wallet_name == HOLDING_WALLET_NAME:
                        wallet_name += " (Holding)"
                        
                    print(f"\n[{i+1}/{len(wallets_needing_more_tao)}] 🔄 Second pass for wallet: {wallet_name}")
                    
                    await harvest_alpha_for_tao_reserve(
                        sub=sub, 
                        wallet=wallet, 
                        netuid=netuid, 
                        target_slippage=args.slippage, 
                        test_mode=TEST_MODE
                    )
                    
                    print("⏳ Waiting before next wallet...")
                    await sub.wait_for_block()
                
    except Exception as e:
        print(f"❌ Error in wallet rotation: {e}")
        print("⏳ Waiting before retry...")
        await asyncio.sleep(BLOCK_TIME_SECONDS)
        
    print("\n✅ Alpha harvesting rotation complete")
    print(f"⏳ Waiting {BLOCK_TIME_SECONDS*2} seconds before next rotation...")
    await asyncio.sleep(BLOCK_TIME_SECONDS * 2)

def initialize_wallet(bt, wallet_name, hotkey_name):
    """Initialize a single wallet with a specific hotkey.
    
    Args:
        bt: The bittensor module
        wallet_name: Name of wallet to unlock
        hotkey_name: Name of hotkey to use
    
    Returns:
        An unlocked wallet instance
    """
    try:
        print(f"🔑 Accessing wallet: {wallet_name} with hotkey: {hotkey_name} for local use only.")
        wallet = bt.wallet(name=wallet_name, hotkey=hotkey_name)
        wallet.unlock_coldkey()
        return wallet
    except Exception as e:
        print(f"\nError accessing wallet: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Parse arguments and set global TEST_MODE
    args = parse_arguments()
    TEST_MODE = args.test

    # Import bittensor after argument parsing to avoid its arguments showing in help
    import bittensor as bt
    
    # Check Bittensor version and warn if needed
    try:
        bt_version = bt.__version__
        print(f"📦 Using Bittensor version: {bt_version}")
        
        # Warn if using a potentially incompatible version (adapt these warnings based on known issues)
        # This is just a warning, not a hard requirement
        if bt_version >= "9.0.0":
            print("ℹ️ Running with Bittensor 9.0.0 or later - robust error handling for API changes is enabled")
    except Exception as e:
        print(f"⚠️ Warning: Could not verify Bittensor version: {e}")
        print("ℹ️ Error handling for potential API incompatibilities is still enabled")

    # Initialize database at the start
    db = SubnetDCADatabase()

    # Add after initializing database
    reports = SubnetDCAReports(db)

    # Process the appropriate wallet(s) before calling main()
    if args.rotate_all_wallets:
        # Rotate all wallets mode - initialize_wallets will handle all wallets
        all_wallets = initialize_wallets(bt)
        try:
            asyncio.run(main(wallets=all_wallets))
        except Exception as e:
            if "MetadataVersioned" in str(e) and "decoded" in str(e):
                print(f"❌ Fatal error with Bittensor API metadata: {e}")
                print("This is likely due to a change in the Bittensor API.")
                print("Try restarting the script or updating Bittensor.")
            elif "NoneType" in str(e) and "offset" in str(e):
                print(f"❌ Fatal error with Bittensor chain data: {e}")
                print("This is likely due to a temporary chain state issue.")
                print("Try restarting the script after a few minutes.")
            else:
                print(f"❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # Single wallet mode (with or without specific hotkey)
        wallet_name = args.wallet
        hotkey_name = args.hotkey
        
        if args.harvest_alpha and wallet_name and not hotkey_name:
            # If harvesting alpha with only wallet specified, initialize all hotkeys for that wallet
            wallet_hotkeys = initialize_wallets(bt, wallet_name=wallet_name)
            try:
                asyncio.run(main(wallets=wallet_hotkeys))
            except Exception as e:
                if "MetadataVersioned" in str(e) and "decoded" in str(e):
                    print(f"❌ Fatal error with Bittensor API metadata: {e}")
                    print("This is likely due to a change in the Bittensor API.")
                    print("Try restarting the script or updating Bittensor.")
                elif "NoneType" in str(e) and "offset" in str(e):
                    print(f"❌ Fatal error with Bittensor chain data: {e}")
                    print("This is likely due to a temporary chain state issue.")
                    print("Try restarting the script after a few minutes.")
                else:
                    print(f"❌ Fatal error: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        else:
            # For single wallet+hotkey, just initialize and continue normally
            single_wallet = initialize_wallet(bt, wallet_name, hotkey_name)
            try:
                asyncio.run(main(single_wallet=single_wallet))
            except Exception as e:
                if "MetadataVersioned" in str(e) and "decoded" in str(e):
                    print(f"❌ Fatal error with Bittensor API metadata: {e}")
                    print("This is likely due to a change in the Bittensor API.")
                    print("Try restarting the script or updating Bittensor.")
                elif "NoneType" in str(e) and "offset" in str(e):
                    print(f"❌ Fatal error with Bittensor chain data: {e}")
                    print("This is likely due to a temporary chain state issue.")
                    print("Try restarting the script after a few minutes.")
                else:
                    print(f"❌ Fatal error: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)

    def signal_handler(signum, frame):
        print("\n⚠️ Received termination signal. Cleaning up...")
        # Close any open connections
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)