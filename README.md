# Bittensor Subnet DCA (dTAO)

The purpose of this script is educational. It demonstrates how to use the bittensor library to create a simple DCA (dTAO) bot for the Bittensor network. The script will chase the EMA of the price of TAO and buy TAO when the price is below the EMA and sell TAO when the price is above the EMA.

## ⚠️ Important Warnings

### Test Mode
It's strongly recommended to first run the bot in test mode to understand its behavior without making actual transactions. Test mode will simulate all operations without performing real stakes/unstakes.

### Supervision Required
This script performs automatic trading operations with real TAO. Do not leave it running unattended unless you fully understand its behavior and intentionally choose to do so. Market conditions can change rapidly, and continuous supervision is recommended during initial usage.

## Setup

### Install python 3.11
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
```

### Clone the repository and install dependencies
```bash
cd $HOME
git clone https://github.com/korbondev/btt-subnet-dca
cd ./btt-subnet-dca

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
```bash
cd $HOME/btt-subnet-dca
source .venv/bin/activate

python3 btt_subnet_dca.py --help  # Show help message and available options
```

### Command Line Arguments

#### Required Arguments:
- `--netuid`: The subnet ID to operate on (e.g., 19 for inference subnet)
- `--wallet`: The name of your wallet
- `--hotkey`: The name of the hotkey to use
- `--slippage`: Target slippage in TAO (e.g., 0.0001). Lower values mean smaller trade sizes
- `--budget`: Maximum TAO budget to use for trading operations

#### Optional Arguments:
- `--test`: Run in test mode without making actual transactions (recommended for first run)

## Examples

### Test Mode Example
Run with test mode to simulate operations without making actual transactions:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.0001 --budget 1 --test
```

### Production Mode Example
Run in production mode with real transactions:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey default --slippage 0.0001 --budget 1
```

## Further Improvements

- Add a more sophisticated wallet management system, perhaps skipping the password prompt
- Add a more sophisticated logging system
- Webhooks to a Telegram channel or Discord server for live monitoring and alerts
- Add configuration file support for persistent settings


## ⚠️ Final Notes

### At your own risk
This script is provided as-is for educational purposes. Use it at your own risk.

### Support
If you need help, please join the [Bittensor Discord](https://discord.gg/qasY3HA9F9) and ask politely for help understanding the concepts in this script.
