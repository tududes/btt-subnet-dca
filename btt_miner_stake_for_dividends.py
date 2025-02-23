import asyncio
from typing import Optional

import bittensor as bt
from bittensor.core.async_subtensor import AsyncSubtensor, StakeInfo
from bittensor.utils.balance import Balance
from bittensor.utils.btlogging import logging
from bittensor_wallet import Wallet

from utils.password_manager import WalletPasswordManager
from btt_subnet_dca import initialize_wallets
from utils.settings import (
    SUBTENSOR, 
    BLOCK_TIME_SECONDS, 
    SAFETY_BALANCE, 
    SLIPPAGE_PRECISION,
    NETUID,
    VALIDATOR_HOTKEY,
    HOLDING_WALLET_NAME,
    HOLDING_WALLET_ADDRESS
)


"""
This script is used to secure the alpha tokens by sending them to the holding wallet.
Then, to also get yield on holdings, we delegate the alpha tokens to the vali hotkey from the holding 
wallet coldkey, while maintaining the same hotkey ownership.

# from btcli 9.0.0 stake movement help
╭─ Stake Movement ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ move       Move staked TAO between hotkeys while keeping the same coldkey ownership.                            │
│ swap       Swap stake between different subnets while keeping the same coldkey-hotkey pair ownership.           │
│ transfer   Transfer stake between coldkeys while keeping the same hotkey ownership.                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
"""


logging.on()
logging.set_debug(True)

async def get_miner_stake(coldkey: str, hotkey: str, subtensor: AsyncSubtensor) -> Balance:  # type: ignore
    stake: dict[int, StakeInfo] = await subtensor.get_stake_for_coldkey_and_hotkey(
        coldkey_ss58=coldkey,
        hotkey_ss58=hotkey,
        netuids=[NETUID],
    )
    stake_alpha = stake.get(NETUID, None)
    logging.debug(f"Stake for {hotkey}: {stake_alpha}")
    return stake_alpha.stake if stake_alpha else Balance.from_float(0, netuid=NETUID)


async def get_hodl_stake_vali(subtensor: AsyncSubtensor) -> Balance:
    stakes: list[StakeInfo] = await subtensor.get_stake_for_coldkey(HOLDING_WALLET_ADDRESS)
    stake_alpha: Optional[StakeInfo] = next((stake for stake in stakes if stake.netuid == NETUID and stake.hotkey_ss58 == VALIDATOR_HOTKEY), None)
    stake: Balance = stake_alpha.stake if stake_alpha else Balance.from_float(0, netuid=NETUID)
    return stake


async def transfer_stake_to_hodl(amount_alpha: Balance, wallet: Wallet, origin_hotkey: str, subtensor: AsyncSubtensor):  # type: ignore
    return await subtensor.transfer_stake(
        wallet=wallet,
        destination_coldkey_ss58=HOLDING_WALLET_ADDRESS,
        hotkey_ss58=origin_hotkey,
        origin_netuid=NETUID,
        destination_netuid=NETUID,
        amount=amount_alpha,
    )


async def delegate_stake_to_vali(amount_alpha: Balance, wallet: Wallet, origin_hotkey: str, subtensor: AsyncSubtensor) -> bool:  # type: ignore
    return await subtensor.move_stake(
        wallet=wallet,
        origin_hotkey=origin_hotkey,
        origin_netuid=NETUID,
        destination_hotkey=VALIDATOR_HOTKEY,
        destination_netuid=NETUID,
        amount=amount_alpha,
    )


async def send_miner_alpha_to_hodl(miner_wallet: Wallet, subtensor: AsyncSubtensor) -> bool:  # type: ignore
    """
    Move all the stake from the miner to the holding wallet.
    """
    miner_coldkey = miner_wallet.coldkeypub.ss58_address
    miner_hotkey = miner_wallet.hotkey.ss58_address

    alpha_amount: Balance = await get_miner_stake(miner_coldkey, miner_hotkey, subtensor)

    success: bool = await transfer_stake_to_hodl(amount_alpha=alpha_amount, wallet=miner_wallet, origin_hotkey=miner_hotkey, subtensor=subtensor)

    return success


async def delegate_hodl_alpha_to_vali(miner_wallet: Wallet, hodl_wallet: Wallet, subtensor: AsyncSubtensor) -> bool:  # type: ignore
    """
    Delegate all the stake from the holding wallet to the vali hotkey.
    The stake is still bound to the original miner hotkey address so it needs to be moved to vali hotkey to accrue yield.
    """
    miner_hotkey = miner_wallet.hotkey.ss58_address

    results: list[bool] = []

    stakes: list[StakeInfo] = await subtensor.get_stake_for_coldkey(HOLDING_WALLET_ADDRESS)

    stakes_to_delegate: list[StakeInfo] = [s for s in stakes if s.netuid == NETUID and s.hotkey_ss58 != VALIDATOR_HOTKEY]

    if len(stakes_to_delegate) > 0:
        hodl_wallet.unlock_coldkey()

    for s in stakes_to_delegate:
        logging.debug(f"Stake on {hodl_wallet.name} that needs to be delegated to vali: {s}")

        stake_to_delegate: Balance = s.stake

        success: bool = await delegate_stake_to_vali(amount_alpha=stake_to_delegate, wallet=hodl_wallet, origin_hotkey=miner_hotkey, subtensor=subtensor)

        results.append(success)

    return all(results)


async def secure_alpha_tokens_and_stake_to_vali():  # type: ignore
    """
    To avoid keeping too much value on a miner key, we need to secure the alpha tokens by sending them to the holding wallet.
    So the logic is this: Transfer the alpha tokens from miner coldkey to holding coldkey.
    Then, to also get yield on holdings, we delegate the alpha tokens to the vali hotkey from the holding wallet.
    This operation does not make a transaction on the alpha token's chart.
    """

    # Initialize password manager for env and unlock wallets
    password_manager = WalletPasswordManager()
    password_manager.load_env()

    # Create and unlock hodl wallet
    hodl_wallet = initialize_wallets(bt, HOLDING_WALLET_NAME)
    if not hodl_wallet:
        print("❌ No hodl wallet was successfully unlocked")
        return
    hodl_wallet = hodl_wallet[0]  # Take the first wallet since we only need one

    # Unlock all miner wallets (excluding hodl wallet)
    miner_wallets = initialize_wallets(bt)
    if not miner_wallets:
        print("❌ No miner wallets found to process")
        return
    
    for wallet in miner_wallets:
        cold_addr = wallet.coldkeypub.ss58_address[:5] + "..."
        hot_addr = wallet.hotkey.ss58_address[:5] + "..."
        print(f"\n🔄 Processing wallet: cold({cold_addr}) hot({hot_addr})")

        async with bt.AsyncSubtensor(SUBTENSOR) as subtensor:

            # Perform stake transfer
            success = await send_miner_alpha_to_hodl(wallet, subtensor)
            if not success:
                print("❌ Failed to transfer stake to hodl wallet")
                continue

            # Delegate to validator
            success = await delegate_hodl_alpha_to_vali(wallet, hodl_wallet, subtensor)
            if not success:
                print("❌ Failed to delegate stake to validator")
                continue

            print("✅ Successfully processed wallet")
            
        await subtensor.close()
        
        # execute one wallet at a time
        break

if __name__ == "__main__":
    asyncio.run(secure_alpha_tokens_and_stake_to_vali())
