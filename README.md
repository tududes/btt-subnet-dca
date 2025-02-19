# 🤖 Bittensor Subnet DCA (dTAO)

The purpose of this script is educational. It demonstrates how to use the bittensor library to create a simple DCA (dTAO) bot for the Bittensor network. The script will chase the EMA of the price of TAO and stake TAO into Alpha when the price is below the EMA and unstake Alpha into TAO when the price is above the EMA.


## 🔍 How It Works

### 📈 EMA Trading Strategy
The script implements a simple trading strategy based on the Exponential Moving Average (EMA) of the TAO price:
- When the current price is **below** the EMA: The script will **stake TAO** to the subnet, effectively "buying" at a lower price
- When the current price is **above** the EMA: The script will **unstake TAO** from the subnet, effectively "selling" at a higher price

This strategy aims to accumulate more TAO over time by consistently buying low and selling high relative to the moving average.

### ⚡ Slippage Auto-Tuning
The script uses a binary search algorithm to automatically find the optimal trade size that matches your target slippage:
1. For each trade, it starts with your remaining budget as the maximum possible trade size

When using `--budget 0`, the script will:
- For staking: Use the full available TAO balance on the coldkey
- For unstaking: Use the full available subnet alpha balance staked to the hotkey (converted to TAO)

2. It then performs a binary search to find the largest trade size that stays within your slippage target
3. If the calculated slippage would be too high, it reduces the trade size
4. If the calculated slippage would be too low, it increases the trade size
5. This process continues until it finds the optimal trade size that matches your target slippage

This auto-tuning ensures that:
- Large trades are broken into smaller pieces to minimize price impact
- Each trade maintains your desired slippage target
- The script adapts to changing market conditions automatically

### 🔄 Wallet Rotation Mode
The script can operate in two modes:
- Single wallet mode (traditional operation)
- Wallet rotation mode (automatically cycles through multiple wallets)

In rotation mode, the script will:
1. Scan your ~/.bittensor/wallets/ directory
2. Prompt for each wallet's password once
3. Initialize all wallet/hotkey pairs
4. Continuously rotate through unlocked wallets
5. Allow skipping remaining wallets by pressing Enter
6. Execute one operation per wallet before moving to next
7. Process up to two hotkeys per coldkey

Note: The script will:
- Cache passwords securely in environment variables
- Perform one stake/unstake operation per wallet before rotating
- Skip remaining wallets if a blank password is entered
- Show truncated wallet addresses during operations for tracking


## ⚠️ Important Warnings

### 🧪 Test Mode
It's strongly recommended to first run the bot in test mode to understand its behavior without making actual transactions. Test mode will simulate all operations without performing real stakes/unstakes.

### 👀 Supervision Required
This script performs automatic trading operations with real TAO. Do not leave it running unattended unless you fully understand its behavior and intentionally choose to do so. Market conditions can change rapidly, and continuous supervision is recommended during initial usage.


## 💡 Important Considerations

### 🔄 Preventing Self-Competition
When running multiple instances of this script, it's important to avoid having your instances compete against each other. Here are some strategies to prevent self-competition:

1. **📊 Price Zone Strategy**:
   - Use the `--min-price-diff` flag to specify how far from the EMA the script should operate
   - Example: Run one instance at 5% from EMA, another at 10% from EMA
   - This creates non-overlapping price zones for each instance
   ```bash
   # Instance 1: Operates when price is 5-10% from EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-01 --hotkey hotkey-01 --min-price-diff 0.05 --slippage 0.0001 --budget 1

   # Instance 2: Operates when price is 10-15% from EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-02 --hotkey hotkey-02 --min-price-diff 0.10 --slippage 0.0001 --budget 1
   ```

2. **↕️ One-Way Operation**:
   - Use the `--one-way-mode` flag to restrict instances to either staking or only unstaking
   - This prevents instances from competing in opposite directions
   ```bash
   # Instance 1: Only stakes when below EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-01 --hotkey hotkey-01 --one-way-mode stake --slippage 0.0001 --budget 1

   # Instance 2: Only unstakes when above EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-02 --hotkey hotkey-02 --one-way-mode unstake --slippage 0.0001 --budget 1
   ```

3. **🔀 Combined Strategy**:
   - Combine price zones with one-way operation for maximum control
   ```bash
   # Instance 1: Stakes only, 5% below EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-01 --hotkey hotkey-01 --one-way-mode stake --min-price-diff 0.05 --slippage 0.0001 --budget 1

   # Instance 2: Unstakes only, 5% above EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-02 --hotkey hotkey-02 --one-way-mode unstake --min-price-diff 0.05 --slippage 0.0001 --budget 1
   ```


## 🛠️ Setup

### 📦 Install python 3.11
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
```

### 📥 Clone the repository and install dependencies
```bash
cd $HOME
git clone https://github.com/korbondev/btt-subnet-dca
cd ./btt-subnet-dca

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 📝 Usage
```bash
cd $HOME/btt-subnet-dca
source .venv/bin/activate

python3 btt_subnet_dca.py --help  # Show help message and available options
```

### 🎮 Command Line Arguments

#### ⚡ Required Arguments:
- `--netuid`: The subnet ID to operate on (e.g., 19 for inference subnet)
- `--wallet`: The name of your wallet
- `--hotkey`: The name of the hotkey to use
- `--slippage`: Target slippage in TAO (e.g., 0.0001). Lower values mean smaller trade sizes
- `--budget`: Maximum TAO budget to use for trading operations (use 0 to use full available balance/stake)

#### 🔧 Optional Arguments:
- `--min-price-diff`: Minimum price difference from EMA to operate (e.g., 0.05 for 5% from EMA)
- `--one-way-mode`: Restrict operations to only staking or only unstaking. Options: stake, unstake (default: both)
- `--test`: Run in test mode without making actual transactions (recommended for first run)
- `--rotate-all-wallets`: Enable wallet rotation mode (cycles through all available wallets)

## 📋 Examples

### 🧪 Test Mode Example
Run with test mode to simulate operations without making actual transactions:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.0001 --budget 1 --test
```

Results:
```
🔑 Accessing wallet: coldkey-01 with hotkey: hotkey-01 for local use only.
Enter your password: 
Decrypting...

📊 Subnet Information (Detailed View)
============================================================

🌐 Network
------------------------------------------------------------
Netuid                   : 19
Subnet                   : inference
Symbol                   : t

👤 Ownership
------------------------------------------------------------
Owner Hotkey             : 5CFJNoUYbd...
Owner Coldkey            : 5CFJNoUYbd...
Registered               : 2023-12-30 04:47:08 UTC

⚙️ Status
------------------------------------------------------------
Is Dynamic               : True
Tempo                    : 360
Last Step                : 4958675
Blocks Since Last Step   : 25

📈 Market
------------------------------------------------------------
Subnet Volume (Alpha)    : t7,550.223801190
Subnet Volume (Tao)      : τ793.161323920
Emission                 : 4.11%
Price (Tao)              : 0.10505
Moving Price (Tao)       : 0.17677
============================================================

🔍 Finding optimal trade size...
  • Testing 0.005000 TAO → 0.000000 slippage

💫 Trade Parameters
----------------------------------------
Size                : 0.005000 TAO
Slippage            : 0.000000 TAO
Budget Left         : 0.010000 TAO
----------------------------------------

📈 Price below EMA - STAKING
🧪 TEST MODE: Would have staked 0.005000 TAO

💰 Wallet Status
----------------------------------------
Balance             : τ2.961664286τ
Stake               : t72.911671858t
----------------------------------------

⏳ Waiting for next block...

(repeats each block)
```

### 🚀 Production Mode Example
Run in production mode with real transactions:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.000001 --budget 0.01
```

Results:
```
🔑 Accessing wallet: coldkey-01 with hotkey: hotkey-01 for local use only.
Enter your password: 
Decrypting...

📊 Subnet Information (Detailed View)
============================================================

🌐 Network
------------------------------------------------------------
Netuid                   : 19
Subnet                   : inference
Symbol                   : t

👤 Ownership
------------------------------------------------------------
Owner Hotkey             : 5CFJNoUYbd...
Owner Coldkey            : 5CFJNoUYbd...
Registered               : 2023-12-30 04:47:04 UTC

⚙️ Status
------------------------------------------------------------
Is Dynamic               : True
Tempo                    : 360
Last Step                : 4958314
Blocks Since Last Step   : 359

📈 Market
------------------------------------------------------------
Subnet Volume (Alpha)    : t7,546.618478178
Subnet Volume (Tao)      : τ794.790116167
Emission                 : 4.11%
Price (Tao)              : 0.10532
Moving Price (Tao)       : 0.17659
============================================================

🔍 Finding optimal trade size...
  • Testing 0.005000 TAO → 0.000000 slippage

💫 Trade Parameters
----------------------------------------
Size                : 0.005000 TAO
Slippage            : 0.000000 TAO
Budget Left         : 0.010000 TAO
----------------------------------------

📈 Price below EMA - STAKING
✅ Successfully staked 0.005000 TAO @ 0.105317

💰 Wallet Status
----------------------------------------
Balance             : τ2.966039286τ
Stake               : t72.069664160t
----------------------------------------

⏳ Waiting for next block...

📊 Status Update
----------------------------------------
Last Step           : 4958675
Blocks Since Last Step: 0
Volume (α)          : 7546.71
Volume (τ)          : 794.73
Price (τ)           : 0.10531
EMA (τ)             : 0.17660
Diff                : -40.37%
----------------------------------------

🔍 Finding optimal trade size...
  • Testing 0.002500 TAO → 0.000000 slippage

💫 Trade Parameters
----------------------------------------
Size                : 0.002500 TAO
Slippage            : 0.000000 TAO
Budget Left         : 0.005000 TAO
----------------------------------------

📈 Price below EMA - STAKING
✅ Successfully staked 0.002500 TAO @ 0.105309

💰 Wallet Status
----------------------------------------
Balance             : τ2.963539286τ
Stake               : t72.894814175t
----------------------------------------

⏳ Waiting for next block...

📊 Status Update
----------------------------------------
Last Step           : 4958675
Blocks Since Last Step: 2
Volume (α)          : 7547.88
Volume (τ)          : 794.80
Price (τ)           : 0.10530
EMA (τ)             : 0.17661
Diff                : -40.38%
----------------------------------------

🔍 Finding optimal trade size...
  • Testing 0.001250 TAO → 0.000000 slippage

💫 Trade Parameters
----------------------------------------
Size                : 0.001250 TAO
Slippage            : 0.000000 TAO
Budget Left         : 0.002500 TAO
----------------------------------------

📈 Price below EMA - STAKING
✅ Successfully staked 0.001250 TAO @ 0.105301

💰 Wallet Status
----------------------------------------
Balance             : τ2.962289286τ
Stake               : t72.906210632t
----------------------------------------

⏳ Waiting for next block...

📊 Status Update
----------------------------------------
Last Step           : 4958675
Blocks Since Last Step: 4
Volume (α)          : 7547.97
Volume (τ)          : 794.74
Price (τ)           : 0.10529
EMA (τ)             : 0.17663
Diff                : -40.39%
----------------------------------------

🔍 Finding optimal trade size...
  • Testing 0.000625 TAO → 0.000000 slippage

💫 Trade Parameters
----------------------------------------
Size                : 0.000625 TAO
Slippage            : 0.000000 TAO
Budget Left         : 0.001250 TAO
----------------------------------------

📈 Price below EMA - STAKING
✅ Successfully staked 0.000625 TAO @ 0.105292

💰 Wallet Status
----------------------------------------
Balance             : τ2.961664286τ
Stake               : t72.911671858t
----------------------------------------

⏳ Waiting for next block...
```

### 🔄 Wallet Rotation Example
Run with wallet rotation to cycle through all available wallets:
```bash
python3 btt_subnet_dca.py --rotate-all-wallets --netuid 19 --slippage 0.0001 --budget 0 --test
```

Note: When using --budget 0 in rotation mode:
- For staking: Uses full available TAO balance
- For unstaking: Uses full available stake converted to TAO


## 🔮 Further Improvements

- 🔐 Update wallet management systemt to optionally skip the password prompt
- 📝 Add a more robust logging system, perhaps to a sqlite database
- 🔔 Webhooks to a Telegram channel or Discord server for live monitoring and alerts
- ⚙️ Add configuration file support for persistent settings


## ⚠️ Final Notes

### ⚖️ At your own risk
This script is provided as-is for educational purposes. Use it at your own risk.

### 💬 Support
If you need help, please read the [Bittensor documentation](https://docs.bittensor.com/) and join the [Bittensor Discord](https://discord.gg/MhsTXDc5), where you could ask politely for help understanding some the concepts in this script. Do not discuss prices or trading strategies, only concepts of working with the Bittensor library.
