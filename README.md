# 🤖 Bittensor Subnet DCA (dTAO)

The purpose of this script is educational. It demonstrates how to use the bittensor library to create a simple DCA (dTAO) bot for the Bittensor network. The script will chase the EMA of the Subnet token Alpha price and stake TAO into Alpha when the price is below the EMA and unstake Alpha into TAO when the price is above the EMA.


## 🔍 How It Works

### 📈 EMA Trading Strategy
The script implements a simple trading strategy based on the Exponential Moving Average (EMA) of the TAO price:
- When the current price is **below** the EMA: The script will **stake TAO** to the subnet, effectively "buying" at a lower price
- When the current price is **above** the EMA: The script will **unstake TAO** from the subnet, effectively "selling" at a higher price

This strategy aims to target an Alpha price along the EMA and accumulate more TAO over time by consistently staking low and unstaking high relative to the Subnet moving average.

### ⚡ Slippage Auto-Tuning
The script uses a binary search algorithm to automatically find the optimal trade size that matches your target slippage:
1. For each trade, it starts with your remaining budget as the maximum possible trade size

When using `--budget 0`, the script will:
- For staking: Use the full available TAO balance on the coldkey
- For unstaking: Use the full available subnet alpha balance staked to the hotkey (converted to TAO)

A safety balance of 1.0 TAO is maintained to prevent completely emptying wallets:
- Staking operations that would reduce balance below 1.0 TAO are skipped
- The wallet is removed from rotation when this occurs
- Unstaking operations are not affected by safety balance

2. It then performs a binary search to find the largest trade size that stays within your slippage target
3. If the calculated slippage would be too high, it reduces the trade size
4. If the calculated slippage would be too low, it increases the trade size
5. This process continues until it finds the optimal trade size that matches your target slippage

This auto-tuning ensures that:
- Large trades are broken into smaller pieces to minimize price impact
- Each trade maintains your desired slippage target
- The script adapts to changing market conditions automatically

### 📊 Dynamic Slippage Control
The script includes an optional dynamic slippage adjustment feature that scales the slippage based on price deviation from the EMA:

#### How It Works
- Maximum slippage (--slippage) is used when price difference exceeds max-price-diff
- Slippage scales down linearly as price approaches min-price-diff
- No slippage applied when price difference is at min-price-diff
- Price difference shows how far price has moved relative to EMA:
  - -50% means price is half of EMA
  - +100% means price is double EMA
  - 0% means price equals EMA

Example output when price is within the min-price-diff:
```
📊 Dynamic Slippage Adjustment
----------------------------------------
Base Slippage       : 0.000100
Min Price Diff      : 5.00%
Max Price Diff      : 20.00%
Current Price Diff  : 15.50%
Scale Factor        : 0.70
Target Slippage     : 0.000730
----------------------------------------
```

Example output when price is beyond the max-price-diff:
```
📊 Dynamic Slippage Adjustment
----------------------------------------
Base Slippage       : 0.000100
Min Price Diff      : 5.00%
Max Price Diff      : 20.00%
Current Price Diff  : -66.67%
Scale Factor        : 1.00
Target Slippage     : 0.000100
----------------------------------------
```

#### Usage
Enable dynamic slippage with these optional flags:
```bash
python3 btt_subnet_dca.py \
    --netuid 19 \
    --wallet coldkey-01 \
    --hotkey hotkey-01 \
    --slippage 0.00001 \
    --min-price-diff 0.05 \
    --max-price-diff 0.20 \
    --dynamic-slippage \
    --test
```

#### Parameters
- `--dynamic-slippage`: Enable dynamic slippage adjustment
- `--min-price-diff`: Price difference where base slippage is used (e.g., 0.05 for 5%)
- `--max-price-diff`: Price difference where maximum slippage is used (e.g., 0.20 for 20%)
- `--slippage`: Base slippage value

This feature allows for:
- Minimal slippage when price is near the EMA
- Gradually increasing slippage as price deviates further
- Maximum slippage (10x base) when price difference exceeds max-price-diff
- Full slippage when price difference exceeds max-price-diff
- Automatic adjustment based on market conditions

### 📊 Database & Reporting
The script maintains a SQLite database to track all operations and provides detailed reporting:

#### Database Features:
- Tracks all wallet operations
- Records transaction success/failure
- Stores historical price data
- Maintains balance history

#### Real-time Reports:
- Activity summaries for 6h, 12h, 24h, 48h, and 72h periods
- Per-wallet statistics
- Transaction counts and volumes
- Price ranges and averages
- ASCII charts of activity
- Success/failure rates

Example Report:
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

### 🔄 Wallet Rotation Modes
The script can operate in several modes:
- Single wallet mode (traditional operation)
- Full wallet rotation mode (automatically cycles through multiple wallets)
- Alpha harvest mode (automatically unstakes excess alpha to maintain reserves)

#### Full Wallet Rotation
In rotation mode, the script will:
1. Scan your ~/.bittensor/wallets/ directory
2. Process coldkeys sequentially in alphabetical order
3. Prompt for each coldkey's password individually
4. Allow skipping to next coldkey by pressing Enter
5. Initialize all hotkeys for successfully unlocked coldkeys
6. Continuously rotate through unlocked wallet/hotkey pairs

#### Wallet/Hotkey Selection Behavior
The script has specific behavior depending on which parameters you provide:

- **With `--rotate-all-wallets`**: Rotates through all available wallets and all hotkeys
- **With `--wallet` only**: Rotates through all hotkeys for the specified wallet
- **With `--wallet` and `--hotkey`**: Uses only the specific wallet/hotkey combination
- **With `--harvest-alpha` and no wallet specified**: Rotates through all available keys

This flexible selection allows you to target operations at different scopes:
- Process your entire wallet collection
- Focus on a single wallet with all its hotkeys
- Target a specific wallet/hotkey pair

Note: The script will:
- Cache passwords securely in environment variables
- Perform one stake/unstake operation per wallet before rotating
- Allow skipping individual coldkeys during initialization
- Continue to next coldkey when one is skipped
- Show truncated wallet addresses during operations for tracking

Example initialization flow:
```
🔐 Initializing wallets for rotation...
============================================================

💼 Processing wallet: coldkey-01 with 14 hotkeys
Enter password for coldkey-01 (or press Enter to skip to next coldkey): 
✅ Successfully unlocked coldkey: coldkey-01
  ✓ Added hotkey: hotkey-01
  ✓ Added hotkey: hotkey-02

💼 Processing wallet: coldkey-02 with 14 hotkeys
Enter password for coldkey-02 (or press Enter to skip to next coldkey): 
⏭️  Skipping coldkey: coldkey-02

💼 Processing wallet: coldkey-03 with 14 hotkeys
...
```

#### 🌱 Alpha Harvest Mode
The script includes a dedicated alpha harvesting mode that:
1. Unstakes excess alpha tokens from wallets 
2. Converts them back to TAO
3. Maintains a minimum alpha reserve in each wallet

Features:
- Processes all wallets in sequence or just a single wallet
- Unstakes only the amount above the configured reserve
- Maintains alpha reserve levels across all wallets
- Supports wallet rotation for batch processing
- Uses binary search to find optimal unstake size with minimal slippage
- Enforces minimum unstake amounts to prevent transaction failures

How to enable:
```bash
# Harvest alpha for all wallets
python3 btt_subnet_dca.py --harvest-alpha --rotate-all-wallets --netuid 19 --slippage 0.00001 --test

# Harvest alpha for a single wallet with all its hotkeys (recommended method)
python3 btt_subnet_dca.py --netuid 19 --harvest-alpha --wallet your-wallet-name --slippage 0.00001

# Harvest alpha for a specific wallet/hotkey pair
python3 btt_subnet_dca.py --harvest-alpha --netuid 19 --wallet your-wallet-name --hotkey hotkey-01 --slippage 0.00001 --test
```

Configuration settings in .env:
```
# Alpha reserve settings
DCA_RESERVE_ALPHA=25.00  # Minimum alpha to maintain in each wallet
DCA_RESERVE_TAO=25.00    # Target TAO to maintain in each wallet
MIN_UNSTAKE_ALPHA=0.1    # Minimum alpha amount to unstake (prevents tiny transaction errors)
MIN_TAO_DEFICIT=0.01     # Minimum TAO deficit to consider worth processing
```

Example output:
```
🔄 Alpha harvesting for wallet: cold(5CqSe...) hot(5DqxK...)
   Current τ balance: 1.668723 τ
   Current α balance: 31.783232 α
   τ reserve target: 25.000000 τ
   α reserve minimum: 25.000000 α
   Current α price: 0.059226 τ
   TAO deficit: 23.331277 τ
   Estimated α needed: 393.936675 α
   Available α for unstaking: 6.783232 α
   Will attempt to unstake: 6.783232 α

🔍 Finding optimal unstake amount with target slippage 0.000100 τ...
  • Testing 3.391616 α → 0.000008 τ slippage, 0.200864 τ expected
  • Testing 5.087424 α → 0.000017 τ slippage, 0.301290 τ expected
  • Testing 5.935328 α → 0.000024 τ slippage, 0.351502 τ expected
  • ...
  • Testing 6.783232 α → 0.000031 τ slippage, 0.401712 τ expected

💫 Unstake Parameters
----------------------------------------
Amount to unstake        : 6.783180 α
Expected TAO received    : 0.401740 τ
Slippage                 : 0.000031 τ
New TAO balance (est)    : 2.070463 τ
New alpha balance (est)  : 25.000052 α
🧪 TEST MODE: Would have unstaked 6.783180 α ≈ 0.401740 τ from cold(5CqSe...) hot(5DqxK...)
```

### ⚙️ Automated Execution with PM2

For production environments, you can use PM2 to run the script as a managed process that automatically restarts on failure and persists across system reboots.

#### Requirements:
Install PM2 if you haven't already:
```bash
# Install PM2 if not already installed
if command -v pm2 &> /dev/null
then
    pm2 startup && pm2 save --force
else
    sudo apt install jq npm -y
    sudo npm install pm2 -g && pm2 update
    npm install pm2@latest -g && pm2 update && pm2 save --force && pm2 startup && pm2 save
fi
```

#### Startup:
Start the script using PM2 for continuous operation:
```bash
cd $HOME/btt-subnet-dca
source .venv/bin/activate

# Start the trade engine with PM2
pm2 start btt_subnet_dca.py --name btt-subnet-dca --interpreter python3 -- --netuid 19 --harvest-alpha --wallet your-wallet-name --slippage 0.00001

# Ensure PM2 starts on system boot
pm2 startup && pm2 save --force

# Watch the logs
pm2 logs btt-subnet-dca
```

#### PM2 Log Management:
Configure log rotation to prevent excessive disk usage:
```bash
# Install pm2-logrotate module if not already installed
pm2 install pm2-logrotate

# Set maximum size of logs to 50M before rotation
pm2 set pm2-logrotate:max_size 50M

# Retain 10 rotated log files
pm2 set pm2-logrotate:retain 10

# Enable compression of rotated logs
pm2 set pm2-logrotate:compress true

# Set rotation interval to every 6 hours
pm2 set pm2-logrotate:rotateInterval '00 */6 * * *'
```

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
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-01 --hotkey hotkey-01 --min-price-diff 0.05 --slippage 0.00001 --budget 1

   # Instance 2: Operates when price is 10-15% from EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-02 --hotkey hotkey-02 --min-price-diff 0.10 --slippage 0.00001 --budget 1
   ```

2. **↕️ One-Way Operation**:
   - Use the `--one-way-mode` flag to restrict instances to either staking or only unstaking
   - This prevents instances from competing in opposite directions
   ```bash
   # Instance 1: Only stakes when below EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-01 --hotkey hotkey-01 --one-way-mode stake --slippage 0.00001 --budget 1

   # Instance 2: Only unstakes when above EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-02 --hotkey hotkey-02 --one-way-mode unstake --slippage 0.00001 --budget 1
   ```

3. **🔀 Combined Strategy**:
   - Combine price zones with one-way operation for maximum control
   ```bash
   # Instance 1: Stakes only, 5% below EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-01 --hotkey hotkey-01 --one-way-mode stake --min-price-diff 0.05 --slippage 0.00001 --budget 1

   # Instance 2: Unstakes only, 5% above EMA
   python3 btt_subnet_dca.py --netuid 19 --wallet wallet-02 --hotkey hotkey-02 --one-way-mode unstake --min-price-diff 0.05 --slippage 0.00001 --budget 1
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

## ⚙️ Environment Configuration

The bot can be configured using environment variables. Create a `.env` file in the root directory by copying the sample:

```bash
cp .env.sample .env
chmod 600 .env  # Restrict file permissions
```

### Available Settings

#### 🌐 Network Settings
- `SUBTENSOR`: Subtensor network endpoint
  - Default: `finney` (mainnet)
  - Alternative: `ws://127.0.0.1:9944` (local subtensor)
- `BLOCK_TIME_SECONDS`: Block time in seconds
  - Default: `12`

#### 💰 Trading Settings
- `DCA_RESERVE_TAO`: Minimum TAO balance to maintain in wallet
  - Default: `1.0`
  - Example: Set to `10.0` to keep at least 10 TAO in wallet
- `DCA_RESERVE_ALPHA`: Minimum alpha balance to maintain when unstaking
  - Default: `1.0`
  - Example: Set to `25.0` to keep at least 25 alpha staked
- `SLIPPAGE_PRECISION`: Target slippage precision in TAO
  - Default: `0.00001`
  - Example: `0.00001` TAO = $0.005 in slippage for $500 TAO
- `MIN_UNSTAKE_ALPHA`: Minimum amount of alpha to unstake in a transaction
  - Default: `0.1`
  - Example: Set to `0.5` to avoid failed transactions with small amounts
  - Transactions below this threshold will be skipped to prevent errors
- `MIN_TAO_DEFICIT`: Minimum TAO deficit to consider worth processing
  - Default: `0.01`
  - Example: Set to `0.1` to be less precise about meeting the exact reserve target
  - Deficits smaller than this are considered "good enough" to avoid endless retries

#### 🔑 Wallet Passwords (Optional)
You can store wallet passwords in the `.env` file using the following format:
```
BT_PW__ROOT__BITTENSOR_WALLETS_<wallet-name>_COLDKEY=<password>
```

Example:
```
BT_PW__ROOT__BITTENSOR_WALLETS_COLDKEY-01_COLDKEY=your-password-here
```

### ⚠️ Security Notes

The `.env` file contains sensitive information. Make sure to:
- Never commit it to version control
- Restrict file permissions (`chmod 600 .env`)
- Back it up securely
- Keep passwords in a secure password manager

### 🔄 Configuration Priority

Settings are applied in the following order (highest to lowest priority):
1. Command line arguments
2. Environment variables from `.env`
3. Default values in code

## 📝 Usage
```bash
cd $HOME/btt-subnet-dca
source .venv/bin/activate

python3 btt_subnet_dca.py --help  # Show help message and available options
```

### 🎮 Command Line Arguments

#### ⚡ Required Arguments:
- `--netuid`: The subnet ID to operate on (e.g., 19 for inference subnet)
- `--wallet`: The name of your wallet (not required with --rotate-all-wallets)
  - When used alone, will rotate through all hotkeys for this wallet
- `--hotkey`: The name of the hotkey to use (not required with --rotate-all-wallets or when rotating through all hotkeys of a wallet)
  - Only specify this if you want to target a single specific wallet/hotkey pair
- `--slippage`: Target slippage in TAO (e.g., 0.00001). Lower values mean smaller trade sizes
- `--budget`: Maximum TAO budget to use for trading operations (use 0 to use full available balance/stake)

#### 🔧 Optional Arguments:
- `--min-price-diff`: Minimum price difference from EMA to operate (e.g., 0.05 for 5% from EMA)
- `--one-way-mode`: Restrict operations to only staking or only unstaking. Options: stake, unstake (default: both)
- `--test`: Run in test mode without making actual transactions (recommended for first run)
- `--rotate-all-wallets`: Enable wallet rotation mode (cycles through all available wallets)
- `--harvest-alpha`: Run in alpha harvesting mode to unstake excess alpha tokens above reserve
- `--dynamic-slippage`: Enable dynamic slippage adjustment

## 📋 Examples

### 🧪 Test Mode Example
Run with test mode to simulate operations without making actual transactions:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.00001 --budget 1 --test
```

### 🚀 Production Mode Example
Run in production mode with real transactions:
```bash
python3 btt_subnet_dca.py --netuid 19 --wallet coldkey-01 --hotkey hotkey-01 --slippage 0.000001 --budget 0.01
```

### 🔄 Wallet Rotation Example
Run with wallet rotation to cycle through all available wallets:
```bash
python3 btt_subnet_dca.py --rotate-all-wallets --netuid 19 --slippage 0.00001 --budget 0 --test
```

Note: When using --budget 0 in rotation mode:
- For staking: Uses full available TAO balance
- For unstaking: Uses full available stake converted to TAO

### 🌱 Alpha Harvesting Example
Run the alpha harvesting mode to unstake excess alpha tokens:
```bash
# Harvest alpha from all wallets (rotates through all wallet/hotkey pairs)
python3 btt_subnet_dca.py --harvest-alpha --rotate-all-wallets --netuid 19 --slippage 0.00001 --test

# Harvest alpha from all hotkeys of a specific wallet (recommended for production)
python3 btt_subnet_dca.py --netuid 19 --harvest-alpha --wallet your-wallet-name --slippage 0.00001

# Harvest alpha from a specific wallet/hotkey pair
python3 btt_subnet_dca.py --harvest-alpha --netuid 19 --wallet your-wallet-name --hotkey hotkey-01 --slippage 0.00001 --test
```

### 📊 Viewing Reports
You can view reports while the bot is running by using reports.py directly:

```bash
# Show overall activity summary
python3 reports.py --summary

# Show statistics for specific wallet
python3 reports.py --wallet 5CnFd... --period 24h

# Show statistics for all wallets
python3 reports.py --all-wallets
```

#### Report Options:
- `--summary`: Show overall activity summary for all time segments
- `--wallet`: Show statistics for specific wallet (provide coldkey address)
- `--period`: Time period for statistics (6h, 12h, 24h, 48h, 72h, 7d, 30d, all)
- `--all-wallets`: Show statistics for all wallets

The reports module can also be imported and used programmatically:
```python
from database import SubnetDCADatabase
from reports import SubnetDCAReports

db = SubnetDCADatabase()
reports = SubnetDCAReports(db)

# Print activity summary
reports.print_summary()

# Print wallet statistics
reports.print_wallet_summary("5CnFd...")
```

## 🔮 Further Improvements

- 🔐 Update wallet management system to optionally skip the password prompt
- 📊 Add graphical visualizations for historical data
- 🔔 Webhooks to a Telegram channel or Discord server for live monitoring and alerts
- ⚙️ Add configuration file support for persistent settings
- 💱 Replace dynamic slippage with dynamic budget scaling:
  - As subnet liquidity grows, slippage becomes less significant
  - Dynamic budget would scale trade size based on price deviation
  - Larger trades when far from EMA, smaller when close
  - More intuitive for deep liquidity pools
  - Easier to configure and understand

## ⚠️ Final Notes

### ⚖️ At your own risk
This script is provided as-is for educational purposes. Use it at your own risk.

### 💬 Support
If you need help, please read the [Bittensor documentation](https://docs.bittensor.com/) and join the [Bittensor Discord](https://discord.gg/MhsTXDc5), where you could ask politely for help understanding some the concepts in this script. Do not discuss prices or trading strategies, only concepts of working with the Bittensor library.

## Secure Stake Movement

The `btt_miner_stake_for_dividends.py` script helps you secure your alpha tokens by moving them to a holding wallet and delegating them to a validator for yield generation. This process involves two steps:

1. Transfer alpha tokens from miner wallet(s) to a secure holding wallet
2. Delegate the transferred tokens to a validator to earn yield

### Backward Compatibility

For now the script only supports one validator, which is the first one in the `VALIDATOR_HOTKEYS` list in the `.env` file.

### Setup

1. Create a new wallet to use as your holding wallet:
```bash
btcli wallet new_coldkey --wallet.name your-holding-wallet
```

2. Configure your `.env` file with the following settings:
```env
# Subnet settings for stake movement
NETUID=19  # The subnet ID (e.g., 19 for inference subnet)
VALIDATOR_HOTKEYS=<validator-hotkey-1>,<validator-hotkey-2>  # Comma-separated list of validator hotkeys to delegate to
HOLDING_WALLET_NAME=your-holding-wallet-name
HOLDING_WALLET_ADDRESS=your-holding-wallet-ss58-address
ALPHA_RESERVE_AMOUNT=10.0  # Amount of alpha to keep in miner wallet
```

### Running the Stake Movement Script with PM2

To run the `btt_miner_stake_for_dividends.py` script continuously in the background using PM2:

```bash
cd $HOME/btt-subnet-dca
source .venv/bin/activate

# Start the stake movement script for the holding wallet (default) with PM2
pm2 start btt_miner_stake_for_dividends.py --name btt-miner-stake --interpreter python3

# Ensure PM2 starts on system boot
pm2 startup && pm2 save --force

# Watch the logs
pm2 logs btt-miner-stake
```

The script will:
1. Run perpetually, checking wallets every 12 hours
2. Transfer excess alpha tokens from miners to your holding wallet
3. Delegate those tokens to your validator to earn yield
4. Automatically restart on failure or system reboot

You can adjust the frequency by modifying the `WAIT_TIME_SECONDS` variable in the script.

#### Command-line Options

The script supports the following command-line arguments:
- `--wallet`: Filter to only process a specific wallet by name (default is your holding wallet)
- `--hotkey`: Filter to only process a specific hotkey by name (requires --wallet to be specified)
- `--all-wallets`: Process all available wallets (overrides --wallet)

If no arguments are provided, the script will use the holding wallet by default. To process all wallets, use the `--all-wallets` flag.