import os
from datetime import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv()

def generate_catalyst_report():
    """
    Scours the web using Gemini's live Google Search grounding to find 
    major crypto/macro catalysts and formulate actionable swing trades.
    """
    try:
        client = genai.Client()
    except Exception as e:
        return f"⚠️ Failed to initialize Gemini Client: {e}"

    prompt = """
    You are an elite Crypto Hedge Fund Swing Trader. 
    Search the web for major crypto and macro catalysts happening in the next 7 to 30 days.
    Look specifically for:
    - Massive Token Unlocks
    - SEC Rulings / ETF Approvals or Denials
    - Major Mainnet Launches, Airdrops, or Protocol Upgrades
    - Institutional Funding Rounds or major acquisitions
    - Major Fed policy shifts affecting crypto

    Identify 1 to 3 highly actionable swing trade setups based on the news you find.
    For each setup, provide:
    1. The Catalyst (What is happening and when)
    2. The Asset Ticker
    3. Trade Direction (LONG or SHORT)
    4. Expected Timeframe
    5. The Setup (Why this catalyst drives price, and where to enter/invalidate)

    Format your output strictly as a highly engaging Discord message using emojis and bold text. 
    Use horizontal rules (---) to separate trades. Do not include standard pleasantries, just the alpha.
    """

    try:
        print("Scouring the web for catalysts...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'tools': [{'google_search': {}}]
            }
        )
        
        report = f"🔥 **Daily Catalyst & Swing Trade Report ({datetime.now().strftime('%Y-%m-%d')})** 🔥\n\n"
        report += response.text
        return report

    except Exception as e:
        print(f"Catalyst Scanner Error: {e}")
        return f"⚠️ Catalyst Scanner failed to generate report: {e}"

if __name__ == "__main__":
    print("Testing Catalyst Scanner...")
    report = generate_catalyst_report()
    print("\n--- DISCORD OUTPUT ---")
    print(report.encode('utf-8').decode('cp1252', 'ignore'))
