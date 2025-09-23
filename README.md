# CryptoTradingAssistant

##Crypto Swing Trading Screener
A Streamlit-based tool for swing trading on KuCoin futures, focusing on top 10 cryptocurrencies by market cap. Fetches real-time price/volume from KuCoin, calculates technical indicators (RSI, EMA, MACD, ATR, Bollinger Bands), and generates a customizable AI prompt for trade setups (5x-15x leverage, $100 trade size, 1:2 risk/reward). Designed for 2025-09-23 market data, prioritizing high-probability setups (RSI <40/>70, BB squeeze <10%, MACD signals).

##Features

Data: Pulls price/volume from KuCoin API (/market/allTickers, /market/candles).
Indicators: RSI (14), EMA (20), MACD (12,26,9), ATR (14), Bollinger Bands (20, 2σ).
Filters: Strong trends (>2% 24h), near 4h low (<2%), near 30d high (>98%), RSI <40/>70, MACD bullish/bearish, BB squeeze (<10%), high probability (RSI+MACD combos).
AI Prompt: Generates editable prompt for swing trade setups, ready for xAI API integration (https://x.ai/api).
UI: Streamlit dashboard with data table, filter outputs, and prompt text area.

##Known Issues

Market Cap: Uses volume * price (inflated, e.g., BTC $5.3T vs. real ~$2.3T). Fix planned: CoinGecko /coins/markets for accurate supply-based cap.
OHLC Gaps: KuCoin’s 4h/7d/30d candles limited (~100 candles), missing full 30d lows (e.g., SOL $185 vs. real ~$120). Fix planned: CoinGecko /ohlc.
Indicators: RSI/MACD occasionally off (e.g., BNB RSI 16.75 miscalculated) due to limited candle data.
No Sentiment: Lacks X/news integration for setup confirmation (e.g., BNB 5.8% pump context).

##Setup

Install Dependencies:pip install streamlit requests pandas numpy


##Clone/Download:
Save crypto_screener_ui.py in a project folder.


Run:streamlit run crypto_screener_ui.py


Opens at http://localhost:8501.
Refreshes every 60s.



##Usage

View Screener:
Top 10 coins by market cap (BTC, ETH, BNB, etc.).
Columns: price, market cap, 24h %, volume, 4h/7d/30d high/low, RSI, EMA, MACD, ATR, BB, probability.


Check Filters:
Strong Trends (>2% 24h), Near 4h Low (<2%), Near 30d High (>98%), etc.
Example: DOGE (RSI 39.30, MACD bullish, BB width 9.25%) flagged as high-probability.


Refine AI Prompt:
Scroll to “AI Prompt for Swing Trading Advice” text area.
Edit prompt (e.g., “Focus on BNB/USDT short” or “Add X sentiment for DOGE bullish”).
Copy for manual AI testing or API integration.


Trade Setup (Example: DOGE Long):
Pair: DOGEUSDTM (KuCoin futures).
Entry: $0.27 (near 4h low).
Target: $0.276 (1.5x ATR $0.004072).
Stop: $0.266 (1x ATR).
Leverage: 10x, $100 trade (~5,000 DOGE).
R:R: 1:2 ($4 risk, $8 gain).
Why: RSI <40, MACD bullish, BB squeeze.



##Refining the AI Prompt
The prompt (in the UI text area) is designed for swing trading setups. Modify it to:

Specify Pairs: “Provide a BNB/USDT short setup.”
Adjust Filters: “Focus on RSI <30, BB width <5%.”
Add Sentiment: “Check X for ‘DOGE bullish’ sentiment.”
Change Leverage: “Use 5x-10x leverage, $200 trade size.”
Example tweak:Based on top 10 crypto screener data (KuCoin futures, 5x-10x leverage):
{df.to_string(index=False)}
Filters: ...
Swing trading advice (2025-09-23 12:30): Suggest a BNB/USDT short setup with entry/exit, 1:2 risk/reward, $100 trade. Use ATR (target ±1.5x, stop ±1x). Prioritize RSI >70, BB squeeze (<5%). Check X for ‘BNB bearish’ sentiment.



##API Integration
To plug the prompt into an AI (e.g., xAI’s Grok):

Copy the prompt from the UI.
Use requests to send to xAI API:import requests
prompt = "YOUR_COPIED_PROMPT"
response = requests.post("https://api.x.ai/v1/grok", json={"prompt": prompt, "key": "YOUR_API_KEY"})
print(response.json())


See https://x.ai/api for API details.

##Debugging

API Errors: “Failed to fetch data” or “Timeout” means KuCoin rate limit. Wait 10 min or use VPN.
NaN Values: Check fetch_top_10() logs; KuCoin may return empty candles.
Inaccurate Data: Market cap/OHLC errors due to KuCoin limitations. Planned fix: CoinGecko integration.
Traceback: Share errors (e.g., crypto_screener_ui.py:123) for quick fixes.


##Notes

Risk: Manual trading on KuCoin futures. Use demo mode first. DYOR!
Account: Optimized for $1,000 account, 2% risk per trade ($20 max loss).
Contact: Share feedback or errors via X (@your_handle) or email.

