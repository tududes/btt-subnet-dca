import os
from dotenv import load_dotenv
import getpass
from pathlib import Path

class WalletPasswordManager:
    def __init__(self, env_path=".env"):
        """Initialize password manager with path to .env file"""
        self.env_path = env_path
        self.env_file = Path(env_path)
        
        # Create .env file if it doesn't exist
        if not self.env_file.exists():
            self.env_file.touch()
        
        # Load existing passwords
        load_dotenv(self.env_path)
        
    def get_env_key(self, wallet_name: str) -> str:
        """Convert wallet name to environment variable key"""
        return f"BT_PW__ROOT__BITTENSOR_WALLETS_{wallet_name.upper()}_COLDKEY"
    
    def get_password(self, wallet_name: str) -> str:
        """Get password from environment or prompt user"""
        env_key = self.get_env_key(wallet_name)
        password = os.getenv(env_key)
        
        if not password:
            try:
                password = getpass.getpass(f"Enter password for {wallet_name} (or press Enter to skip): ")
            except getpass.GetPassWarning:
                password = input(f"Enter password for {wallet_name} (or press Enter to skip): ")
                
            # Allow skipping via empty password
            if not password.strip():
                return None
            
            # Ask about saving only if a password was entered
            save = input("Would you like to save this password for future use? [y/N]: ").lower()
            if save in ['y', 'yes']:
                self.save_password(wallet_name, password)
                print(f"✅ Password saved for {wallet_name}")
        else:
            print(f"✅ Using stored password for {wallet_name}")
        
        return password
    
    def save_password(self, wallet_name: str, password: str):
        """Save password to .env file"""
        env_key = self.get_env_key(wallet_name)
        
        # Read existing contents
        if self.env_file.exists():
            current_contents = self.env_file.read_text()
        else:
            current_contents = ""
            
        # Remove existing entry if present
        lines = [line for line in current_contents.splitlines() 
                if not line.startswith(f"{env_key}=")]
        
        # Add new password
        lines.append(f"{env_key}={password}")
        
        # Write back to file
        self.env_file.write_text("\n".join(lines) + "\n")
        
        # Reload environment
        load_dotenv(self.env_path)
    
    def clear_password(self, wallet_name: str):
        """Remove password from .env file"""
        env_key = self.get_env_key(wallet_name)
        
        if self.env_file.exists():
            current_contents = self.env_file.read_text()
            lines = [line for line in current_contents.splitlines() 
                    if not line.startswith(f"{env_key}=")]
            self.env_file.write_text("\n".join(lines) + "\n")
            
        # Reload environment
        load_dotenv(self.env_path) 