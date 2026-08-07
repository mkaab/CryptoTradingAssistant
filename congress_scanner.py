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
        
    prompt = """
    You are an elite political trading analyst.
    Search the web for the most recent U.S. Congressional stock trades and disclosures (made within the last 7 days).
    Check resources like Quiver Quantitative, Capitol Trades, Unusual Whales, or recent news articles.
    
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
    """
    
    try:
        print("Scouring the web for Congressional trades...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{'google_search': {}}]
            )
        )
        
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
    archive_file = "ai_trade_history.json"
    history = []
    
    if os.path.exists(archive_file):
        try:
            with open(archive_file, "r") as f:
                history = json.load(f)
        except Exception:
            history = []
            
    # Append timestamp to each trade
    today = datetime.now().strftime("%Y-%m-%d")
    for trade in trades:
        trade['date_issued'] = today
        history.append(trade)
        
    with open(archive_file, "w") as f:
        json.dump(history, f, indent=4)
    print(f"Saved {len(trades)} structured congressional predictions for future backtesting.")


if __name__ == "__main__":
    print("Testing Congress Scanner...")
    report = generate_congress_report()
    print("\n--- DISCORD OUTPUT ---")
    print(report.encode('utf-8').decode('cp1252', 'ignore'))
