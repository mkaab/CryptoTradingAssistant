import os
import json
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def generate_catalyst_report():
    """
    Scours the web using Gemini's live Google Search grounding to find 
    major crypto/macro catalysts and formulate actionable swing trades.
    Returns both the formatted Discord string and saves the structured JSON for backtesting.
    """
    try:
        client = genai.Client()
    except Exception as e:
        return f"⚠️ Failed to initialize Gemini Client: {e}"
        
    # --- GET LIVE CONTEXT TO PREVENT HALLUCINATIONS ---
    live_prices = "CURRENT SPOT PRICES:\n"
    try:
        from data_manager import get_historical_data
        for symbol in ["BTC-USD", "ETH-USD", "SOL-USD"]:
            df = get_historical_data(symbol, "1d", 3)
            if not df.empty:
                current_price = df.iloc[-1]['close']
                live_prices += f"{symbol}: ${current_price:.2f}\n"
    except Exception as e:
        live_prices += "Error fetching live prices.\n"

    # --- GET ACTIVE POSITIONS FOR UPDATES ---
    active_positions = "ACTIVE SWING TRADES (PAST PREDICTIONS):\n"
    try:
        from file_store import read_file
        content = read_file("ai_trade_history.json")
        if content:
            history = json.loads(content)
            # Just grab the last 5 trades so we don't overwhelm the prompt
            recent_trades = history[-5:] if len(history) > 5 else history
            active_positions += json.dumps(recent_trades, indent=2)
        else:
            active_positions += "No active positions yet."
    except Exception:
        active_positions += "Error reading history."

    prompt = f"""
    You are an elite Hedge Fund Swing Trader. 
    Search the web for major macro, forex, gold (XAUUSD), and crypto catalysts happening in the next 7 to 30 days.
    
    {live_prices}
    DO NOT hallucinate prices. If you are predicting Entry/TP/SL for BTC, ETH, or SOL, base your math EXACTLY on the current spot prices provided above!

    {active_positions}
    You must also act as a Position Manager. Review the ACTIVE SWING TRADES above. In your discord_message, add a section called "**Updates on Active Trades**". 
    If a trade from yesterday (or a 3-month long position) needs its Stop Loss raised to break-even, or partial profits taken due to shifting market conditions, state it clearly!
    Look specifically for:
    - Major Central Bank Rate Decisions or Fed policy shifts (for Forex/Gold)
    - Geopolitical escalations or supply chain shocks (for Gold)
    - Massive Crypto Token Unlocks
    - SEC Rulings / ETF Approvals or Denials
    - Major Mainnet Launches, Airdrops, or Protocol Upgrades

    Identify 1 to 3 highly actionable swing trade setups based on the news you find.
    
    CRITICAL DEDUPLICATION RULE: DO NOT output a trade setup if a highly similar setup for the exact same catalyst already exists in the ACTIVE SWING TRADES history above. Only output GENUINELY NEW catalysts. If you only find old news, return an empty trades array.
    
    You MUST output valid JSON only. Your JSON must match this exact schema:
    {{
        "trades": [
            {{
                "catalyst_title": "string",
                "ticker": "string (e.g. BTC-USD, XAU=F)",
                "direction": "LONG or SHORT",
                "timeframe": "string",
                "entry_price": float (use the most aggressive entry price in the range),
                "take_profit": float,
                "stop_loss": float,
                "setup_context": "string (Why this catalyst drives price)"
            }}
        ],
        "discord_message": "string (The highly engaging Discord message using emojis and bold text, formatting the trades)"
    }}
    
    For the entry_price, take_profit, and stop_loss, they MUST be floats (numbers). If the price is a range, use the most aggressive price in the range (i.e. the best entry price closest to the stop loss).
    Make sure your discord_message contains horizontal rules (---) separating the new trades, and a dedicated "**Updates on Active Trades**" section. Do not include standard pleasantries, just the alpha.
    CRITICAL: YOU MUST ESCAPE ALL DOUBLE QUOTES (") INSIDE YOUR discord_message AND setup_context STRINGS USING A BACKSLASH (\"). IF YOU USE UNESCAPED QUOTES, OUR SYSTEM WILL CRASH WITH A JSON DECODING ERROR!
    """

    try:
        print("Scouring the web for catalysts and generating structured data...")
        from llm_utils import generate_with_retry
        response = generate_with_retry(
            client=client,
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{'google_search': {}}]
            )
        )
        
        if not response.text:
            raise ValueError("Gemini API returned an empty response. (Possible safety filter block or API timeout)")
            
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        try:
            data = json.loads(raw_text.strip(), strict=False)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON from Gemini. Raw text was:\n{raw_text}")
            raise e
        
        # Save structured data for the AI Evaluator
        save_predictions_to_archive(data['trades'])
        
        report = f"🔥 **Daily Catalyst & Swing Trade Report ({datetime.now().strftime('%Y-%m-%d')})** 🔥\n\n"
        report += data['discord_message']
        return report

    except Exception as e:
        print(f"Catalyst Scanner Error: {e}")
        return f"⚠️ Catalyst Scanner failed to generate report: {e}"

def save_predictions_to_archive(trades):
    # Save to history
    archive_file = "ai_trade_history.json"
    try:
        from file_store import read_file, write_file
        content = read_file(archive_file)
        if content:
            history = json.loads(content)
        else:
            history = []
    except Exception:
        history = []
        
    # Append timestamp to each trade
    today = datetime.now().strftime("%Y-%m-%d")
    for trade in trades:
        trade['date_issued'] = today
        history.append(trade)
    
    try:
        write_file(archive_file, json.dumps(history, indent=4))
    except Exception as e:
        print(f"Error saving history: {e}")
        
    print(f"Saved {len(trades)} structured predictions to {archive_file} for future backtesting.")

if __name__ == "__main__":
    print("Testing Catalyst Scanner...")
    report = generate_catalyst_report()
    print("\n--- DISCORD OUTPUT ---")
    print(report.encode('utf-8').decode('cp1252', 'ignore'))
