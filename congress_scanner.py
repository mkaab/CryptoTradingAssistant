import os
import json
from datetime import datetime
import google.genai as genai
from google.genai import types

def generate_congress_report():
    """
    Uses Gemini's live Google Search grounding to find recent 
    Congressional stock trades and formats them for Discord.
    Also extracts the JSON for the AI Evaluator.
    """
    try:
        client = genai.Client()
    except Exception as e:
        return f"⚠️ Failed to initialize Gemini Client: {e}"
        
    # --- GET ACTIVE POSITIONS FOR UPDATES ---
    active_positions = "ACTIVE CONGRESSIONAL TRADES (PAST PREDICTIONS):\n"
    try:
        from file_store import read_file
        content = read_file("ai_trade_history.json")
        if content:
            history = json.loads(content)
            recent_trades = history[-5:] if len(history) > 5 else history
            active_positions += json.dumps(recent_trades, indent=2)
        else:
            active_positions += "No active positions yet."
    except Exception:
        active_positions += "Error reading history."
        
    prompt = """
    You are an elite political trading analyst.
    Search the web for the most recent U.S. Congressional stock trades and disclosures (made within the last 7 days).
    Check resources like Quiver Quantitative, Capitol Trades, Unusual Whales, or recent news articles.
    
    {active_positions}
    
    CRITICAL DEDUPLICATION RULE: DO NOT output a trade setup if a highly similar setup for the exact same politician and exact same ticker already exists in the ACTIVE CONGRESSIONAL TRADES history above. Only output GENUINELY NEW disclosures. If you only find old news, return an empty trades array.
    
    You MUST output valid JSON only. Your JSON must match this exact schema:
    {
        "trades": [
            {
                "catalyst_title": "string (Politician's Name & Role)",
                "ticker": "string",
                "direction": "LONG or SHORT (Buy=LONG, Sell=SHORT)",
                "timeframe": "string (e.g. Medium-term)",
                "entry_price": float (estimate the closing price of the day it was traded, or just 0 if unknown),
                "take_profit": float (estimate a 20% gain from entry),
                "stop_loss": float (estimate a 10% loss from entry),
                "setup_context": "string (Why this is interesting, committee assignments etc.)"
            }
        ],
        "discord_message": "string (The highly engaging Discord message using emojis and bold text, formatting the trades)"
    }
    
    Format the discord_message as a clear, highly readable alert for a Discord trading channel.
    Limit it to the 3 most significant or interesting trades.
    
    Use formatting like:
    🏛️ **Nancy Pelosi (D-CA)**
    **Action:** BOUGHT $NVDA
    **Amount:** $1M - $5M
    **Dates:** Traded on 2026-07-20 (Disclosed: 2026-08-01)
    **Context:** Sits on committee relevant to semiconductors...
    
    If no new trades have been disclosed in the last 7 days, your discord_message should say "No major congressional trades disclosed this week." and trades array should be empty.
    CRITICAL: YOU MUST ESCAPE ALL DOUBLE QUOTES (") INSIDE YOUR discord_message AND setup_context STRINGS USING A BACKSLASH (\"). IF YOU USE UNESCAPED QUOTES, OUR SYSTEM WILL CRASH WITH A JSON DECODING ERROR!
    """
    
    try:
        print("Scouring the web for Congressional trades...")
        from llm_utils import generate_with_retry
        response = generate_with_retry(
            client=client,
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(tools=[{"google_search": {}}], temperature=0.3)
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
            
        data = json.loads(raw_text.strip())
        
        # Save structured data for the AI Evaluator
        if len(data.get('trades', [])) > 0:
            save_predictions_to_archive(data['trades'])
        
        report = f"🦅 **Capitol Hill Insider Trading Report ({datetime.now().strftime('%Y-%m-%d')})** 🦅\n\n"
        report += data['discord_message']
        return report

    except Exception as e:
        print(f"Congress Scanner Error: {e}")
        return f"⚠️ Congress Scanner failed to generate report: {e}"

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
        if 'date_issued' not in trade:
            trade['date_issued'] = today
        history.append(trade)
    
    try:
        write_file(archive_file, json.dumps(history, indent=4))
    except Exception as e:
        print(f"Error saving history: {e}")
        
    print(f"Saved {len(trades)} congressional trades to {archive_file} for future backtesting.")


if __name__ == "__main__":
    print("Testing Congress Scanner...")
    report = generate_congress_report()
    print("\n--- DISCORD OUTPUT ---")
    print(report.encode('utf-8').decode('cp1252', 'ignore'))
