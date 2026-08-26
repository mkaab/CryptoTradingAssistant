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
        
    # --- GET LIVE CONTEXT (HTF Candlesticks) ---
    live_prices = "CURRENT 1D CANDLESTICKS (Last 5 Days):\n"
    try:
        from data_manager import get_historical_data
        for symbol in ["BTC-USD", "ETH-USD", "SOL-USD", "GC=F"]: # Included GC=F (Gold)
            df = get_historical_data(symbol, "1d", 5)
            if not df.empty:
                live_prices += f"\n{symbol}:\n"
                for index, row in df.iterrows():
                    date_str = row['time'].strftime('%Y-%m-%d') if hasattr(row['time'], 'strftime') else row['time']
                    live_prices += f"  {date_str} - O: {row['open']:.2f}, H: {row['high']:.2f}, L: {row['low']:.2f}, C: {row['close']:.2f}\n"
    except Exception as e:
        live_prices += f"Error fetching live prices: {e}\n"

    # --- GET ACTIVE POSITIONS FOR UPDATES ---
    active_positions = "ACTIVE SWING TRADES (PAST PREDICTIONS):\n"
    try:
        from db import get_engine
        import pandas as pd
        engine = get_engine()
        active_df = pd.read_sql("SELECT * FROM active_ai_trades", engine)
        if not active_df.empty:
            active_positions += active_df.to_json(orient='records', indent=2)
        else:
            active_positions += "No active positions yet."
    except Exception:
        active_positions += "Error reading history from database or table is empty."

    prompt = f"""
    You are an elite Hedge Fund Swing Trader. 
    Search the web for major macro, forex, gold (XAUUSD), and crypto catalysts happening in the next 7 to 30 days.
    
    {live_prices}
    HTF BIAS CHECK: Analyze the Daily (1D) Candlesticks provided above. Do NOT recommend a LONG if the asset is heavily overextended (e.g., 3-4 consecutive green days making new highs). Establish your Higher Timeframe bias using these candlestick patterns before determining your entry price. DO NOT hallucinate prices. Base your math EXACTLY on the current spot prices provided above!

    {active_positions}
    CRITICAL CONSISTENCY RULES (Position Management):
    1. DO NOT issue a new trade for a catalyst/asset if we already have an active trade for it!
    2. DO NOT flip-flop your bias (e.g. going LONG today when you went SHORT yesterday on the same event).
    3. If new news contradicts your previous thesis on an active trade, write an update in the "**Updates on Active Trades**" section suggesting we close the old position, rather than issuing a conflicting new trade.
    
    Look specifically for:
    - Major Central Bank Rate Decisions or Fed policy shifts (for Forex/Gold)
    - Geopolitical escalations or supply chain shocks (for Gold)
    - Massive Crypto Token Unlocks
    - SEC Rulings / ETF Approvals or Denials
    - Major Mainnet Launches, Airdrops, or Protocol Upgrades

    Identify 1 to 3 highly actionable swing trade setups based on the news you find. If you only find old news, return an empty trades array.

    
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
    if not trades:
        return
        
    # Append timestamp to each trade
    today = datetime.now().strftime("%Y-%m-%d")
    for trade in trades:
        trade['date_issued'] = today
        # Ensure status is OPEN
        trade['status'] = 'OPEN'
    
    try:
        from db import get_engine
        import pandas as pd
        engine = get_engine()
        df = pd.DataFrame(trades)
        df.to_sql('active_ai_trades', engine, if_exists='append', index=False)
        print(f"✅ Saved {len(trades)} structured predictions to 'active_ai_trades' Postgres table.")
    except Exception as e:
        print(f"❌ Error saving to Postgres active_ai_trades: {e}")

if __name__ == "__main__":
    print("Testing Catalyst Scanner...")
    report = generate_catalyst_report()
    print("\n--- DISCORD OUTPUT ---")
    print(report.encode('utf-8').decode('cp1252', 'ignore'))
