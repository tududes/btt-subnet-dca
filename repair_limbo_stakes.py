import asyncio
from typing import List

import bittensor as bt
from bittensor.core.async_subtensor import AsyncSubtensor, StakeInfo
from bittensor.utils.balance import Balance
from bittensor.utils.btlogging import logging
from bittensor_wallet import Wallet

from utils.password_manager import WalletPasswordManager
from btt_subnet_dca import initialize_wallets
from utils.settings import (
    SUBTENSOR, 
    NETUID,
    VALIDATOR_HOTKEYS,
    HOLDING_WALLET_NAME,
    HOLDING_WALLET_ADDRESS,
)

# Import the delegate function from the original script
from btt_miner_stake_for_dividends import delegate_stake_to_vali

logging.on()
logging.set_debug(True)

# Extract the first validator hotkey
VALIDATOR_HOTKEY = VALIDATOR_HOTKEYS[0]


async def find_limbo_stakes(subtensor: AsyncSubtensor) -> List[StakeInfo]:
    """
    Find all stakes in the holding wallet that are NOT on the validator hotkey.
    These are stakes in limbo that need to be delegated.
    """
    print(f"\n🔍 Searching for limbo stakes in holding wallet...")
    
    # Get all stakes for the holding wallet
    stakes: List[StakeInfo] = await subtensor.get_stake_for_coldkey(HOLDING_WALLET_ADDRESS)
    
    # Filter for stakes on NETUID that are NOT on validator hotkey
    limbo_stakes = [s for s in stakes if s.netuid == NETUID and s.hotkey_ss58 != VALIDATOR_HOTKEY]
    
    print(f"📊 Found {len(limbo_stakes)} stakes in limbo (not on validator hotkey)")
    
    # Print details of each limbo stake
    for i, stake in enumerate(limbo_stakes):
        print(f"   {i+1}. Hotkey: {stake.hotkey_ss58[:8]}... | Amount: {float(stake.stake):.6f} α")
    
    return limbo_stakes


async def repair_limbo_stakes():
    """
    Main repair function that:
    1. Initializes the holding wallet
    2. Finds all stakes not on validator hotkey
    3. Delegates each one to the validator hotkey
    """
    
    # Initialize password manager
    password_manager = WalletPasswordManager()
    password_manager.load_env()
    
    # Initialize holding wallet
    print(f"🔐 Initializing holding wallet: {HOLDING_WALLET_NAME}")
    hodl_wallets = initialize_wallets(bt, HOLDING_WALLET_NAME)
    if not hodl_wallets:
        print("❌ Failed to initialize holding wallet")
        return
    
    hodl_wallet = hodl_wallets[0]
    print(f"✅ Holding wallet initialized: {hodl_wallet.coldkeypub.ss58_address[:8]}...")
    
    async with bt.AsyncSubtensor(SUBTENSOR) as subtensor:
        
        # Find all limbo stakes
        limbo_stakes = await find_limbo_stakes(subtensor)
        
        if not limbo_stakes:
            print("\n✨ No limbo stakes found! All stakes are properly delegated.")
            return
        
        # Unlock holding wallet for delegation
        hodl_wallet.unlock_coldkey()
        
        # Process each limbo stake
        print(f"\n🔧 Starting repair process...")
        success_count = 0
        
        for i, stake in enumerate(limbo_stakes):
            print(f"\n📍 Processing stake {i+1}/{len(limbo_stakes)}")
            print(f"   Hotkey: {stake.hotkey_ss58}")
            print(f"   Amount: {float(stake.stake):.6f} α")
            
            try:
                # Delegate to validator hotkey
                print(f"   🔄 Delegating to validator hotkey...")
                success = await delegate_stake_to_vali(
                    amount_alpha=stake.stake,
                    wallet=hodl_wallet,
                    origin_hotkey=stake.hotkey_ss58,
                    subtensor=subtensor
                )
                
                if success:
                    print(f"   ✅ Successfully delegated!")
                    success_count += 1
                else:
                    print(f"   ❌ Delegation failed")
                    
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                logging.error(f"Failed to delegate stake from {stake.hotkey_ss58}: {e}")
        
        # Summary
        print(f"\n📊 Repair Summary:")
        print(f"   - Total limbo stakes found: {len(limbo_stakes)}")
        print(f"   - Successfully repaired: {success_count}")
        print(f"   - Failed: {len(limbo_stakes) - success_count}")
        
        # Verify final state
        print(f"\n🔍 Verifying final state...")
        remaining_limbo = await find_limbo_stakes(subtensor)
        
        if not remaining_limbo:
            print("✅ All stakes successfully delegated to validator!")
        else:
            print(f"⚠️  {len(remaining_limbo)} stakes still in limbo")
        
        await subtensor.close()


async def show_current_state():
    """
    Helper function to show current state of all stakes in holding wallet
    """
    print(f"\n📊 Current State of Holding Wallet Stakes")
    print("=" * 60)
    
    async with bt.AsyncSubtensor(SUBTENSOR) as subtensor:
        stakes = await subtensor.get_stake_for_coldkey(HOLDING_WALLET_ADDRESS)
        
        # Group by hotkey
        validator_stakes = []
        limbo_stakes = []
        
        for stake in stakes:
            if stake.netuid == NETUID:
                if stake.hotkey_ss58 == VALIDATOR_HOTKEY:
                    validator_stakes.append(stake)
                else:
                    limbo_stakes.append(stake)
        
        # Show validator stakes
        print(f"\n✅ Stakes on Validator Hotkey ({VALIDATOR_HOTKEY[:8]}...):")
        total_validator = 0
        for stake in validator_stakes:
            amount = float(stake.stake)
            total_validator += amount
            print(f"   - {amount:.6f} α")
        print(f"   Total: {total_validator:.6f} α")
        
        # Show limbo stakes
        print(f"\n⚠️  Stakes in Limbo (not on validator):")
        total_limbo = 0
        for stake in limbo_stakes:
            amount = float(stake.stake)
            total_limbo += amount
            print(f"   - Hotkey: {stake.hotkey_ss58[:8]}... | Amount: {amount:.6f} α")
        print(f"   Total: {total_limbo:.6f} α")
        
        print(f"\n📊 Summary:")
        print(f"   - Total on validator: {total_validator:.6f} α")
        print(f"   - Total in limbo: {total_limbo:.6f} α")
        print(f"   - Grand total: {total_validator + total_limbo:.6f} α")
        
        await subtensor.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Repair limbo stakes in holding wallet')
    parser.add_argument('--show-state', '-s', action='store_true', 
                        help='Show current state without making changes')
    
    args = parser.parse_args()
    
    if args.show_state:
        asyncio.run(show_current_state())
    else:
        print("🔧 Starting limbo stake repair process...")
        print("This will delegate all non-validator stakes to the validator hotkey")
        asyncio.run(repair_limbo_stakes())


if __name__ == "__main__":
    main() 