import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
WALLETS_FILE = "tracked_wallets.json"
STATE_FILE = "wallet_tracker_state.json"

def send_discord_alert(message):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
        for chunk in chunks:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": chunk})
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")

def load_tracked_wallets():
    from file_store import read_file, write_file
    content = read_file(WALLETS_FILE)
    if content:
        return json.loads(content)
    # Create a default config if nothing exists
    dummy_wallets = {
        "0x0000000000000000000000000000000000000000": "Vitalik Buterin (Example)",
        "0x503828976D22510aad0201ac7EC88293211D23Da": "Smart Meme Trader"
    }
    write_file(WALLETS_FILE, json.dumps(dummy_wallets, indent=4))
    return dummy_wallets

def load_state():
    from file_store import read_file
    content = read_file(STATE_FILE)
    if content:
        return json.loads(content)
    return {}

def save_state(state):
    from file_store import write_file
    write_file(STATE_FILE, json.dumps(state, indent=4))

def check_wallet_activity(address, nickname, state):
    """
    Checks Etherscan for recent ERC-20 token transfers for the given address.
    """
    if not ETHERSCAN_API_KEY:
        print("⚠️ ETHERSCAN_API_KEY is missing. Cannot track ETH wallets.")
        return []
        
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&page=1&offset=50&sort=desc&apikey={ETHERSCAN_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("status") != "1":
            return [] # No transactions or error
            
        transactions = data.get("result", [])
        new_alerts = []
        last_tx_hash = state.get(address, "")
        
        for tx in transactions:
            tx_hash = tx.get("hash")
            
            # Stop if we hit a transaction we've already processed
            if tx_hash == last_tx_hash:
                break
                
            token_symbol = tx.get("tokenSymbol")
            token_name = tx.get("tokenName")
            value_raw = float(tx.get("value", 0))
            decimals = int(tx.get("tokenDecimal", 18))
            value_formatted = value_raw / (10 ** decimals)
            
            to_addr = tx.get("to", "").lower()
            
            # Determine if Buy (Incoming to Wallet) or Sell (Outgoing from Wallet)
            # This is a simplification; in reality, a buy is transferring WETH to a DEX router and receiving a Token.
            # But seeing an incoming token transfer is a good proxy for "Accumulating".
            if to_addr == address.lower():
                action = "ACCUMULATING (Buy / Transfer In)"
                emoji = "🟢"
            else:
                action = "DISTRIBUTING (Sell / Transfer Out)"
                emoji = "🔴"
                
            # Filter out tiny dust transactions to avoid spam
            if value_formatted > 0:
                alert = (
                    f"{emoji} **Whale Alert: {nickname}** {emoji}\n"
                    f"**Action:** {action}\n"
                    f"**Token:** {token_name} (${token_symbol})\n"
                    f"**Amount:** {value_formatted:,.2f} {token_symbol}\n"
                    f"**Wallet:** `{address}`\n"
                    f"**Tx Hash:** [View on Etherscan](https://etherscan.io/tx/{tx_hash})"
                )
                new_alerts.append(alert)
                
        # Update state to the newest transaction hash
        if transactions:
            state[address] = transactions[0].get("hash")
            
        return new_alerts
        
    except Exception as e:
        print(f"Error checking wallet {address}: {e}")
        return []

def run_tracker():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running Whale Tracker...")
    wallets = load_tracked_wallets()
    state = load_state()
    
    all_alerts = []
    
    for address, nickname in wallets.items():
        # Etherscan rate limit is 5 req/sec on free tier
        time.sleep(0.5) 
        alerts = check_wallet_activity(address, nickname, state)
        all_alerts.extend(alerts)
        
    save_state(state)
    
    if all_alerts:
        print(f"Found {len(all_alerts)} new whale movements!")
        # We don't want to spam 50 messages if a whale did a massive wash trade.
        # Cap at 5 alerts per run, or combine them.
        for alert in all_alerts[:5]:
            send_discord_alert(alert)
            time.sleep(1) # Sleep to avoid Discord rate limits
        
        if len(all_alerts) > 5:
            send_discord_alert(f"⚠️ *And {len(all_alerts) - 5} more transactions were suppressed to avoid spam.*")
    else:
        print("No new whale movements detected.")

if __name__ == "__main__":
    run_tracker()
