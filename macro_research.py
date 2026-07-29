import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_crypto_sentiment(symbol="BTCUSDT"):
    """
    Fetches the Global Long/Short Account Ratio from Binance Futures.
    This acts as the crypto equivalent of a COT report.
    """
    try:
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1d"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data and isinstance(data, list) and len(data) > 0:
            latest = data[-1] # Newest data point
            long_ratio = float(latest['longAccount'])
            short_ratio = float(latest['shortAccount'])
            ls_ratio = float(latest['longShortRatio'])
            
            # Interpret the data
            if ls_ratio > 1.5:
                bias = "Heavily Long (Crowd is Bullish)"
            elif ls_ratio < 0.7:
                bias = "Heavily Short (Crowd is Bearish)"
            else:
                bias = "Neutral/Mixed"
                
            return {
                "ratio": ls_ratio,
                "long_percent": long_ratio * 100,
                "short_percent": short_ratio * 100,
                "bias": bias,
                "raw": latest
            }
    except Exception as e:
        print(f"Error fetching crypto sentiment: {e}")
        
    return None

def get_economic_calendar():
    """
    Fetches today's US Economic Events using Finnhub.
    Looking for High Impact events like FOMC, CPI, NFP.
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        return {"error": "No FINNHUB_API_KEY found in .env"}
        
    try:
        # Get today's date in YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={today}&token={api_key}"
        
        response = requests.get(url, timeout=10)
        
        # If API key is invalid, Finnhub usually returns 401 or 403
        if response.status_code != 200:
            return {"error": f"API Error: {response.status_code}"}
            
        data = response.json()
        events = data.get("economicCalendar", [])
        
        high_impact_events = []
        
        for event in events:
            # We only care about USA events for global macro
            if event.get("country") == "US":
                event_name = event.get("event", "").upper()
                
                # Check if it's a major event
                is_major = any(keyword in event_name for keyword in ["FOMC", "FED", "CPI", "INFLATION", "NONFARM", "NFP"])
                
                if is_major or event.get("impact") == "high":
                    high_impact_events.append({
                        "time": event.get("time"),
                        "event": event.get("event"),
                        "impact": "High"
                    })
                    
        return {"events": high_impact_events}
        
    except Exception as e:
        print(f"Error fetching economic calendar: {e}")
        return {"error": str(e)}

def generate_daily_context():
    """
    Compiles sentiment and economic data into a Daily Macro Report.
    Returns the report string and a risk_modifier string (NORMAL, REDUCED, NO_TRADE).
    """
    report = "📊 **Daily Macro & Sentiment Context** 📊\n"
    risk_modifier = "NORMAL"
    
    # 1. Crypto Sentiment (Retail Positioning)
    sentiment = get_crypto_sentiment()
    if sentiment:
        report += f"\n**Retail Sentiment (BTC)**\n"
        report += f"L/S Ratio: {sentiment['ratio']:.2f}\n"
        report += f"Longs: {sentiment['long_percent']:.1f}% | Shorts: {sentiment['short_percent']:.1f}%\n"
        report += f"Bias: {sentiment['bias']}\n"
        
        # If retail is heavily one-sided, we might want to fade them
        if sentiment['ratio'] > 2.0 or sentiment['ratio'] < 0.5:
            report += "⚠️ *Retail is extremely one-sided. Watch for heavy liquidity sweeps.*\n"
    else:
        report += "\n**Retail Sentiment**: Unavailable\n"
        
    # 2. Daily Backtest Results Update
    backtest_stats = "\n**Latest Backtest Performance (SMC Model)**\n"
    try:
        if os.path.exists("backtest_results.md"):
            with open("backtest_results.md", "r") as f:
                bt = f.read()
                # Parse out Win Rate and PnL
                win_rate = [line for line in bt.split('\n') if 'Win Rate' in line]
                pnl = [line for line in bt.split('\n') if 'Net PnL' in line]
                if win_rate and pnl:
                    backtest_stats += f"{win_rate[0].replace('- ', '')}\n"
                    backtest_stats += f"{pnl[0].replace('- ', '')}\n"
        else:
            backtest_stats += "No backtest data available.\n"
    except:
        backtest_stats += "Failed to parse backtest results.\n"
        
    report += backtest_stats
        
    # 3. Economic Calendar (News Risk)
    eco_cal = get_economic_calendar()
    
    report += f"\n**US Economic Calendar (Today)**\n"
    if "error" in eco_cal:
        report += f"⚠️ {eco_cal['error']} (Skipping News Filter)\n"
    else:
        events = eco_cal.get("events", [])
        if not events:
            report += "No major US economic events today. Clear skies.\n"
        else:
            report += "🚨 **HIGH IMPACT EVENTS DETECTED:**\n"
            for e in events:
                # Convert UTC string to a cleaner format if possible, or just print
                report += f"- {e['event']} ({e['time']} UTC)\n"
            
            # Since there is a high impact event today, we reduce risk.
            risk_modifier = "REDUCED"
            report += "\n⚠️ *Risk Modifier: REDUCED (Halve your position size due to news volatility)*\n"
            
    return report, risk_modifier, sentiment

if __name__ == "__main__":
    # Test the module
    report, risk, sentiment = generate_daily_context()
    print(report.encode('utf-8').decode('cp1252', 'ignore'))
    print(f"Risk Status: {risk}")
