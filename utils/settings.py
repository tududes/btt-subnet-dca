import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Network settings
SUBTENSOR = os.getenv('SUBTENSOR', 'finney')
BLOCK_TIME_SECONDS = int(os.getenv('BLOCK_TIME_SECONDS', '12'))

# Subnet settings
NETUID = int(os.getenv('NETUID', '0'))
VALIDATOR_HOTKEY = os.getenv('VALIDATOR_HOTKEY', '')
HOLDING_WALLET_NAME = os.getenv('HOLDING_WALLET_NAME', '')
HOLDING_WALLET_ADDRESS = os.getenv('HOLDING_WALLET_ADDRESS', '')
ALPHA_RESERVE_AMOUNT = float(os.getenv('ALPHA_RESERVE_AMOUNT', '0.0'))  # Amount of alpha to keep in miner wallet

# Trading settings
SAFETY_BALANCE = float(os.getenv('SAFETY_BALANCE', '1.0'))
SLIPPAGE_PRECISION = float(os.getenv('SLIPPAGE_PRECISION', '0.0001')) 