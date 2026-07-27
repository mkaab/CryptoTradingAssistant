import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from google import genai
from google.genai import types

# Import data fetcher from our existing bot
from bot_runner import fetch_candles, TARGET_SYMBOLS

load_dotenv()

# Setup Gemini Client
# Uses GEMINI_API_KEY from environment
try:
    client = genai.Client()
except Exception as e:
    print(f"Failed to initialize Gemini Client. Did you set GEMINI_API_KEY? Error: {e}")
    client = None

CONFIG_FILE = "ai_strategy_config.json"
JOURNAL_FILE = "ai_journal.md"

def get_todays_price_action():
    """Fetches a high-level summary of today's price action for the AI to read."""
    summary = ""
    for symbol in TARGET_SYMBOLS:
        # Fetch today's 4H data to get the broader trend
        df = fetch_candles(symbol, '4H')
        if df.empty:
            continue
            
        # Get only the last 24 hours of data (6 candles on 4H)
        today_df = df.tail(6)
        
        open_price = today_df.iloc[0]['open']
        close_price = today_df.iloc[-1]['close']
        high_price = today_df['high'].max()
        low_price = today_df['low'].min()
        
        move_pct = ((close_price - open_price) / open_price) * 100
        volatility_pct = ((high_price - low_price) / low_price) * 100
        
        summary += f"\nSymbol: {symbol}\n"
        summary += f"- Open: {open_price:.4f} | Close: {close_price:.4f}\n"
        summary += f"- Net Move: {move_pct:.2f}%\n"
        summary += f"- Volatility (High-Low spread): {volatility_pct:.2f}%\n"
    
    return summary

def run_agent(client, persona_prompt, data_context):
    """Generic function to run an agent prompt."""
    if not client:
        return "ERROR: Gemini API Key missing."
        
    full_prompt = f"{persona_prompt}\n\nDATA CONTEXT:\n{data_context}\n\nProvide your analysis:"
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt,
        )
        return response.text
    except Exception as e:
        print(f"Agent Error: {e}")
        return f"Agent failed to respond: {e}"

def run_night_shift():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Hedge Fund AI Night Shift...")
    
    # 1. Gather Data
    print("Gathering market data...")
    market_data = get_todays_price_action()
    
    # Load bot's PnL or trade history (for now, simulated as we don't track PnL yet)
    bot_stats = "Bot Status: Online. No severe drawdowns reported today. Standard operating parameters."
    
    # 2. Run Technical Quant
    print("Running Technical Quant Analysis...")
    quant_prompt = (
        "You are the Lead Quantitative Analyst. You focus purely on math, price action, and trend structure. "
        "Review the OHLCV net movements and volatility for the day. "
        "Is the market trending strongly, or is it choppy? "
        "Keep your report under 3 paragraphs."
    )
    quant_report = run_agent(client, quant_prompt, market_data)
    
    # 3. Run Risk Manager
    print("Running Risk Management Analysis...")
    risk_prompt = (
        "You are the Chief Risk Officer, modeled after Market Wizards like Paul Tudor Jones. "
        "Your only job is capital preservation. Review the volatility in the market data and the bot's status. "
        "Should we widen our stop losses due to chop, or keep them tight? "
        "Keep your report under 3 paragraphs."
    )
    risk_report = run_agent(client, risk_prompt, f"Market Data:\n{market_data}\n\nBot Stats:\n{bot_stats}")
    
    # 4. Run Portfolio Manager (Orchestrator)
    print("Running Portfolio Manager Orchestration...")
    pm_prompt = (
        "You are the Head Portfolio Manager. You synthesize reports from your Quant and Risk Manager. "
        "Based on their reports, you must output a STRICT JSON configuration file that will dictate how the trading bot behaves tomorrow.\n"
        "Your output must be ONLY valid JSON, no markdown formatting, no backticks.\n"
        "The JSON MUST follow this exact structure:\n"
        "{\n"
        '  "whipsaw_buffer_pct": 0.2, // increase to 0.3 or 0.4 if risk manager says volatility is high\n'
        '  "allowed_direction": "BOTH", // can be "LONG_ONLY", "SHORT_ONLY", or "BOTH" based on quant trend\n'
        '  "base_rr_multiplier": 2 // usually 2, increase to 3 if market is trending beautifully\n'
        "}\n"
    )
    
    pm_context = f"--- QUANT REPORT ---\n{quant_report}\n\n--- RISK REPORT ---\n{risk_report}"
    pm_decision_json = run_agent(client, pm_prompt, pm_context)
    
    # Clean the JSON output (LLMs sometimes wrap it in ```json)
    cleaned_json = pm_decision_json.replace('```json', '').replace('```', '').strip()
    
    # Save the Strategy Config
    try:
        config_data = json.loads(cleaned_json)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
        print("✅ Strategy Config updated successfully.")
    except Exception as e:
        print(f"❌ Failed to parse Portfolio Manager JSON. Error: {e}")
        print(f"Raw Output: {pm_decision_json}")
        
    # Save the Journal
    journal_content = f"# AI Hedge Fund Journal ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    journal_content += f"## Technical Quant Report\n{quant_report}\n\n"
    journal_content += f"## Risk Manager Report\n{risk_report}\n\n"
    journal_content += f"## Portfolio Manager Decision\n```json\n{cleaned_json}\n```\n"
    
    with open(JOURNAL_FILE, "w") as f:
        f.write(journal_content)
        
    print(f"✅ Night Shift complete. Journal saved to {JOURNAL_FILE}.")

if __name__ == "__main__":
    run_night_shift()
