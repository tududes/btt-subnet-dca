# Bittensor Subnet DCA (dTAO)

The purpose of this script is educational. It demonstrates how to use the bittensor library to create a simple DCA (dTAO) bot for the Bittensor network. The script will chase the EMA of the price of TAO and buy TAO when the price is below the EMA and sell TAO when the price is above the EMA.

## ⚠️ Important Warnings

### Test Mode
It's strongly recommended to first run the bot in test mode to understand its behavior without making actual transactions. Test mode will simulate all operations without performing real stakes/unstakes.

### Supervision Required
This script performs automatic trading operations with real TAO. Do not leave it running unattended unless you fully understand its behavior and intentionally choose to do so. Market conditions can change rapidly, and continuous supervision is recommended during initial usage.

To run in test mode, simply add the --test flag to your command:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --slippage 0.0001 --budget 1 --test
```

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

python3 btt_subnet_dca.py --netuid <netuid> --wallet <wallet_name> --slippage <slippage_target> --budget <max_tao_budget> [--test]
```

### Arguments
- `--netuid`: The subnet ID to operate on
- `--wallet`: The name of your wallet
- `--slippage`: Target slippage in TAO (e.g., 0.0001τ)
- `--budget`: Maximum TAO budget to use
- `--test`: Optional flag to run in test mode without making actual transactions

## Example
This will run the script on the subnet with the wallet named `coldkey-01` with a slippage target of `0.0001τ` and a max tao budget of `1τ`. You will be prompted to enter your wallet password as per the native bittensor CLI.
```bash
# Test mode example:
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --slippage 0.0001 --budget 1 --test

# Production mode example:
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --slippage 0.0001 --budget 1
```

### Example of a successful run in test mode
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --slippage 0.0001 --budget 0.25 --test
```

## Further Improvements

- Add a more sophisticated wallet management system, perhaps skipping the password prompt
- Add a more sophisticated logging system
- Webhooks to a Telegram channel or Discord server for live monitoring and alerts

## ⚠️ Final Notes

### At your own risk
This script is provided as-is for educational purposes. Use it at your own risk.

### Support
If you need help, please join the [Bittensor Discord](https://discord.gg/qasY3HA9F9) and ask politely for help understanding the concepts in this script.
