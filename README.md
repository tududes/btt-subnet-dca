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

Results:
```
Enter your password: 
Decrypting...

Subnet Information:
--------------------------------------------------
netuid                   : 19
Subnet                   : inference
Symbol                   : t
Owner Hotkey             : 5CFJNoUYbd...
Owner Coldkey            : 5CFJNoUYbd...
Registered               : 2023-12-30 04:47:06 UTC
Is Dynamic               : True
Tempo                    : 360
Last Step                : 4958314
Blocks Since Last Step   : 87
Subnet Volume (Alpha)    : t7,505.975722193
Subnet Volume (Tao)      : τ775.657893458
Emission                 : 4.11%
Price (Tao)              : 0.10334
Moving Price (Tao)       : 0.17474
--------------------------------------------------
DEBUG - increment: 0.500000, slippage: 0.001346, raw: (t4.837111367, t0.001346272)
DEBUG - increment: 0.250000, slippage: 0.000337, raw: (t2.418892196, t0.000336624)
DEBUG - increment: 0.125000, slippage: 0.000084, raw: (t1.209530244, t0.000084165)
Final increment: 0.125000 (slippage: 0.000084)
Remaining budget: 1.000000
Price is below moving_price! STAKE TAO TO SUBNET!
slippage for subnet 19 (t1.209530244, t0.000084165)
TEST MODE: Would have staked 0.125 TAO
netuid 19 stake added: increment 0.125 @ price 0.103338716
wallet balance: τ2.971039286τ
netuid 19 stake: t0.000000000t

Subnet Information:
--------------------------------------------------
netuid                   : 19
Subnet                   : inference
Symbol                   : t
Owner Hotkey             : 5CFJNoUYbd...
Owner Coldkey            : 5CFJNoUYbd...
Registered               : 2023-12-30 04:47:00 UTC
Is Dynamic               : True
Tempo                    : 360
Last Step                : 4958314
Blocks Since Last Step   : 88
Subnet Volume (Alpha)    : t7,506.025800985
Subnet Volume (Tao)      : τ775.637030133
Emission                 : 4.11%
Price (Tao)              : 0.10334
Moving Price (Tao)       : 0.17475
--------------------------------------------------
DEBUG - increment: 0.437500, slippage: 0.001031, raw: (t4.232761746, t0.001030813)
DEBUG - increment: 0.218750, slippage: 0.000258, raw: (t2.116638536, t0.000257744)
DEBUG - increment: 0.109375, slippage: 0.000064, raw: (t1.058383696, t0.000064444)
Final increment: 0.109375 (slippage: 0.000064)
Remaining budget: 0.875000
Price is below moving_price! STAKE TAO TO SUBNET!
slippage for subnet 19 (t1.058383696, t0.000064444)
TEST MODE: Would have staked 0.109375 TAO
netuid 19 stake added: increment 0.109375 @ price 0.103335247
wallet balance: τ2.971039286τ
netuid 19 stake: t0.000000000t
```

### Production Mode Example
Run in production mode with real transactions:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.0001 --budget 1
```

Results:
```
Enter your password: 
Decrypting...

Subnet Information:
--------------------------------------------------
netuid                   : 19
Subnet                   : inference
Symbol                   : t
Owner Hotkey             : 5CFJNoUYbd...
Owner Coldkey            : 5CFJNoUYbd...
Registered               : 2023-12-30 04:47:06 UTC
Is Dynamic               : True
Tempo                    : 360
Last Step                : 4958314
Blocks Since Last Step   : 52
Subnet Volume (Alpha)    : t7,503.693284840
Subnet Volume (Tao)      : τ777.063492234
Emission                 : 4.11%
Price (Tao)              : 0.10356
Moving Price (Tao)       : 0.17451
--------------------------------------------------
DEBUG - increment: 0.005000, slippage: 0.000000, raw: (t0.048282235, t0.000000133)
Final increment: 0.005000 (slippage: 0.000000)
Remaining budget: 0.010000
Price is below moving_price! STAKE TAO TO SUBNET!
slippage for subnet 19 (t0.048282235, t0.000000133)
netuid 19 stake added: increment 0.005 @ price 0.10355747
wallet balance: τ2.975414286τ
netuid 19 stake: t0.000000000t

Subnet Information:
--------------------------------------------------
netuid                   : 19
Subnet                   : inference
Symbol                   : t
Owner Hotkey             : 5CFJNoUYbd...
Owner Coldkey            : 5CFJNoUYbd...
Registered               : 2023-12-30 04:47:00 UTC
Is Dynamic               : True
Tempo                    : 360
Last Step                : 4958314
Blocks Since Last Step   : 54
Subnet Volume (Alpha)    : t7,503.830742892
Subnet Volume (Tao)      : τ776.967458249
Emission                 : 4.11%
Price (Tao)              : 0.10354
Moving Price (Tao)       : 0.17452
--------------------------------------------------
DEBUG - increment: 0.002500, slippage: 0.000000, raw: (t0.024144578, t0.000000032)
Final increment: 0.002500 (slippage: 0.000000)
Remaining budget: 0.005000
Price is below moving_price! STAKE TAO TO SUBNET!
slippage for subnet 19 (t0.024144578, t0.000000032)
netuid 19 stake added: increment 0.0025 @ price 0.103542775
wallet balance: τ2.972914286τ
netuid 19 stake: t0.000000000t

Subnet Information:
--------------------------------------------------
netuid                   : 19
Subnet                   : inference
Symbol                   : t
Owner Hotkey             : 5CFJNoUYbd...
Owner Coldkey            : 5CFJNoUYbd...
Registered               : 2023-12-30 04:47:00 UTC
Is Dynamic               : True
Tempo                    : 360
Last Step                : 4958314
Blocks Since Last Step   : 56
Subnet Volume (Alpha)    : t7,503.958763196
Subnet Volume (Tao)      : τ776.874307691
Emission                 : 4.11%
Price (Tao)              : 0.10353
Moving Price (Tao)       : 0.17454
--------------------------------------------------
DEBUG - increment: 0.001250, slippage: 0.000000, raw: (t0.012073951, t0.000000006)
Final increment: 0.001250 (slippage: 0.000000)
Remaining budget: 0.002500
Price is below moving_price! STAKE TAO TO SUBNET!
slippage for subnet 19 (t0.012073951, t0.000000006)
netuid 19 stake added: increment 0.00125 @ price 0.103528595
wallet balance: τ2.971664286τ
netuid 19 stake: t0.000000000t
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
If you need help, please read the [Bittensor documentation](https://docs.bittensor.com/) and join the [Bittensor Discord](https://discord.gg/MhsTXDc5), where you could ask politely for help understanding some the concepts in this script. Do not discuss prices or trading strategies, only concepts of working with the Bittensor library.
