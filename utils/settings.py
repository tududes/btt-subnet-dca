import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Network settings
SUBTENSOR = os.getenv('SUBTENSOR', 'finney')
BLOCK_TIME_SECONDS = int(os.getenv('BLOCK_TIME_SECONDS', '12'))

# Trading settings
SAFETY_BALANCE = float(os.getenv('SAFETY_BALANCE', '1.0'))
SLIPPAGE_PRECISION = float(os.getenv('SLIPPAGE_PRECISION', '0.0001')) 