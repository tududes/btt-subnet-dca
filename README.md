# Bittensor Subnet DCA (dTAO)

The purpose of this script is educational. It demonstrates how to use the bittensor library to create a simple DCA (dTAO) bot for the Bittensor network. The script will chase the EMA of the price of TAO and buy TAO when the price is below the EMA and sell TAO when the price is above the EMA.

## Important: Test Mode

It's strongly recommended to first run the bot in test mode to understand its behavior without making actual transactions. Test mode will simulate all operations without performing real stakes/unstakes.

To run in test mode, simply add TEST_MODE=true before your command:
```bash
TEST_MODE=true python3 btt_subnet_dca.py <netuid> <wallet_name> <slippage_target> <max_tao_budget>
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

# Test mode (recommended for first run):
TEST_MODE=true python btt_subnet_dca.py <netuid> <wallet_name> <slippage_target> <max_tao_budget>

# Production mode (after testing):
python3 btt_subnet_dca.py <netuid> <wallet_name> <slippage_target> <max_tao_budget>
```

## Example
This will run the script on the subnet with the wallet named `coldkey-01` with a slippage target of `0.0001τ` and a max tao budget of `5τ`. You will be prompted to enter your wallet password as per the native bittensor CLI.
```bash
cd $HOME/btt-subnet-dca
source .venv/bin/activate

# Test mode example:
TEST_MODE=true python3 btt_subnet_dca.py 19 coldkey-01 0.0001 5

# Production mode example:
python3 btt_subnet_dca.py 19 coldkey-01 0.0001 5
```
