import asyncio
import sys
import os
import argparse
from datetime import datetime, timedelta, timezone

# Constants
BLOCK_TIME_SECONDS = 12   
SLIPPAGE_PRECISION = 0.0001  # Precision of 0.0001 tao ($0.05 in slippage for $500 TAO)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='''
🤖 Bittensor DCA (dTAO) bot for automated staking/unstaking based on EMA.
This script will chase the EMA of the price of TAO and:
📈 Buy TAO when the price is below the EMA
📉 Sell TAO when the price is above the EMA

💡 Example usage:
  python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.0001 --budget 1 --min-price-diff 0.05 --test
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog='btt_subnet_dca.py'
    )
    
    # Required arguments
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
        required=True,
        help='💼 The name of your wallet'
    )
    required.add_argument(
        '--hotkey',
        type=str,
        required=True,
        help='🔑 The name of the hotkey to use'
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
        help='💰 Maximum TAO budget to use for trading operations'
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

    # Print help if no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    return args

args = parse_arguments()


# Import bittensor after argument parsing to avoid its arguments showing in help
import bittensor as bt


TEST_MODE = args.test

try:
    print(f"🔑 Accessing wallet: {args.wallet} with hotkey: {args.hotkey} for local use only.")
    wallet = bt.wallet(name=args.wallet, hotkey=args.hotkey)
    wallet.unlock_coldkey()
except Exception as e:
    print(f"\nError accessing wallet: {e}")
    sys.exit(1)

async def chase_ema(netuid, wallet):
    remaining_budget = args.budget  # Initialize remaining budget
    iteration_count = 0  # Track iterations
    
    async with bt.AsyncSubtensor('finney') as sub:
        while remaining_budget > 0:  # Continue only if we have budget left
            subnet_info = await sub.subnet(netuid)
            
            alpha_price = float(subnet_info.price.tao)
            moving_price = float(subnet_info.moving_price) * 1e11
            price_diff_pct = abs(alpha_price - moving_price) / moving_price

            # Skip if price difference is less than minimum required
            if price_diff_pct < args.min_price_diff:
                print(f"\n⏳ Price difference ({price_diff_pct:.2%}) < minimum required ({args.min_price_diff:.2%})")
                print("💤 Waiting for larger price movement...")
                await sub.wait_for_block()
                iteration_count += 1
                continue

            # Show full details on first run, compact view afterwards
            if iteration_count == 0:
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
                        ('Owner Hotkey', subnet_info.owner_hotkey[:10] + "..."),
                        ('Owner Coldkey', subnet_info.owner_coldkey[:10] + "..."),
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

            # Binary search with remaining budget as max
            target_slippage = args.slippage  # in tao
            min_increment = 0.0
            max_increment = min(1.0, remaining_budget)
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
            print(f"{'Budget Left':20}: {remaining_budget:.6f} TAO")
            print("-" * 40)

            if increment > remaining_budget:
                print("❌ Insufficient remaining budget")
                break

            # Decrement budget by the amount used
            remaining_budget -= abs(increment)

            if alpha_price > moving_price:
                if args.one_way_mode == 'stake':
                    print("⏭️  Price above EMA but stake-only mode active. Skipping...")
                    await sub.wait_for_block()
                    iteration_count += 1
                    continue
                    
                print("\n📉 Price above EMA - UNSTAKING")
                
                if not TEST_MODE:
                    try:
                        await sub.unstake( 
                            wallet = wallet, 
                            netuid = netuid,
                            amount = bt.Balance.from_tao(increment), 
                        )
                        print(f"✅ Successfully unstaked {increment:.6f} TAO @ {alpha_price:.6f}")
                    except Exception as e:
                        print(f"❌ Error unstaking: {e}")
                else:
                    print(f"🧪 TEST MODE: Would have unstaked {increment:.6f} TAO")

            elif alpha_price < moving_price:
                if args.one_way_mode == 'unstake':
                    print("⏭️  Price below EMA but unstake-only mode active. Skipping...")
                    await sub.wait_for_block()
                    iteration_count += 1
                    continue
                    
                print("\n📈 Price below EMA - STAKING")

                if not TEST_MODE:
                    try:
                        await sub.add_stake( 
                            wallet = wallet, 
                            netuid = netuid,
                            amount = bt.Balance.from_tao(increment), 
                        )
                        print(f"✅ Successfully staked {increment:.6f} TAO @ {alpha_price:.6f}")
                    except Exception as e:
                        print(f"❌ Error staking: {e}")
                else:
                    print(f"🧪 TEST MODE: Would have staked {increment:.6f} TAO")

            else:
                print("🦄 Price equals EMA - No action needed")
                iteration_count += 1
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

            print("\n⏳ Waiting for next block...")
            await sub.wait_for_block()
            iteration_count += 1

        print(f"\n✨ Budget exhausted. Total used: {args.budget - remaining_budget:.6f} TAO")

async def main():
    # perpetually chase the EMA
    while True:
        await chase_ema(args.netuid, wallet)

asyncio.run(main())