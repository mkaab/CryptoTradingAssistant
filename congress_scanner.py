import os
from datetime import datetime
import google.genai as genai

def generate_congress_report():
    """
    Uses Gemini's live Google Search grounding to find recent 
    Congressional stock trades and formats them for Discord.
    """
    try:
        client = genai.Client()
    except Exception as e:
        return f"⚠️ Failed to initialize Gemini Client: {e}"
        
    prompt = """
    You are an elite political trading analyst.
    Search the web for the most recent U.S. Congressional stock trades and disclosures (made within the last 7 days).
    Check resources like Quiver Quantitative, Capitol Trades, Unusual Whales, or recent news articles.
    
    Format the response as a clear, highly readable alert for a Discord trading channel.
    Limit it to the 3 most significant or interesting trades.
    
    For each trade, include:
    - The Politician's Name & Party/Role
    - The Ticker / Company
    - Buy or Sell?
    - The estimated amount or range (e.g., $100k - $250k)
    - The exact Date Traded and the Date Disclosed
    - A 1-sentence analysis on why this is interesting (e.g. committee assignments, pending legislation, etc.)
    
    Use formatting like:
    🏛️ **Nancy Pelosi (D-CA)**
    **Action:** BOUGHT $NVDA
    **Amount:** $1M - $5M
    **Dates:** Traded on 2026-07-20 (Disclosed: 2026-08-01)
    **Context:** Sits on committee relevant to semiconductors...
    
    If no new trades have been disclosed in the last 7 days, just say "No major congressional trades disclosed this week."
    """
    
    try:
        print("Scouring the web for Congressional trades...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'tools': [{'google_search': {}}]
            }
        )
        
        report = f"🦅 **Capitol Hill Insider Trading Report ({datetime.now().strftime('%Y-%m-%d')})** 🦅\n\n"
        report += response.text
        return report

    except Exception as e:
        print(f"Congress Scanner Error: {e}")
        return f"⚠️ Congress Scanner failed to generate report: {e}"

if __name__ == "__main__":
    print("Testing Congress Scanner...")
    report = generate_congress_report()
    print("\n--- DISCORD OUTPUT ---")
    print(report.encode('utf-8').decode('cp1252', 'ignore'))
