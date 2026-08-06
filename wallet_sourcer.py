import os
import json
import requests
import re

WALLETS_FILE = "tracked_wallets.json"

def load_tracked_wallets():
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_tracked_wallets(wallets):
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=4)
    print(f"✅ Saved {len(wallets)} wallets to {WALLETS_FILE}")

def scrape_solana_top_holders(token_address, token_name, limit=20):
    """
    Uses the Solscan Public API to fetch the top holders of a Solana SPL token.
    No API key required for the public endpoint (though rate limited).
    """
    url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&offset=0&limit={limit}"
    
    print(f"Fetching top {limit} holders for {token_name} ({token_address}) on Solana...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch from Solscan. HTTP {response.status_code}")
            return
            
        data = response.json()
        holders = data.get("data", [])
        
        wallets = load_tracked_wallets()
        added = 0
        
        for i, holder in enumerate(holders):
            address = holder.get("address")
            amount = holder.get("amount")
            # Exclude known exchange wallets if possible, usually they have massive amounts and are labeled on Solscan
            # but public API might not have tags. We'll just add them as "Whale"
            if address and address not in wallets:
                nickname = f"{token_name} Whale #{i+1}"
                wallets[address] = nickname
                added += 1
                
        save_tracked_wallets(wallets)
        print(f"🎉 Successfully sourced {added} new whale wallets for {token_name}!")
        
    except Exception as e:
        print(f"❌ Error scraping Solscan: {e}")

def manual_add():
    wallets = load_tracked_wallets()
    print("\n--- Manual Wallet Entry ---")
    address = input("Enter Wallet Address (0x... or Solana Address): ").strip()
    
    if not address:
        return
        
    nickname = input("Enter a nickname for this wallet (e.g. 'PEPE Sniper'): ").strip()
    
    wallets[address] = nickname
    save_tracked_wallets(wallets)
    print(f"Added {nickname} to tracking list!")

if __name__ == "__main__":
    print("🐋 Welcome to the Whale Sourcer 🐋")
    print("1. Scrape Top Holders of a Solana Token")
    print("2. Manually add an Ethereum/Solana Wallet")
    
    choice = input("Select an option (1/2): ").strip()
    
    if choice == "1":
        address = input("Enter Solana SPL Token Address (e.g. WIF or BONK contract): ").strip()
        name = input("Enter Token Ticker/Name: ").strip()
        scrape_solana_top_holders(address, name)
    elif choice == "2":
        manual_add()
    else:
        print("Invalid choice.")
