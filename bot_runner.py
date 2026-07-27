import requests
import pandas as pd
from datetime import datetime
import time
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Config & Setup ---
BASE_URL = "https://api.kucoin.com"
TARGET_SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "EURUSD=X", "GBPUSD=X", "GC=F"]
STATE_FILE = "last_signal.json"

import yfinance as yf

# Notification Settings
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# --- Notification Functions ---
def send_discord_alert(message):
    if not DISCORD_WEBHOOK_URL:
        return
    data = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")

def send_alert(message):
    print(f"\n{message}\n") # Always print to console
    send_discord_alert(message)

# --- State Management ---
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# --- Helper Functions ---
def make_request(url, max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        time.sleep(delay)
    return None

def fetch_candles(symbol, timeframe):
    if "-USDT" in symbol:
        if timeframe == '4H':
            interval = '4hour'
        elif timeframe == '5m':
            interval = '5min'
        else:
            interval = '5min'
            
        url = f"{BASE_URL}/api/v1/market/candles?type={interval}&symbol={symbol}"
        data = make_request(url)
        
        if data and 'data' in data:
            df = pd.DataFrame(data['data'], columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            df['time'] = pd.to_datetime(df['time'].astype(int), unit='s')
            for col in ['open', 'close', 'high', 'low', 'volume']:
                df[col] = df[col].astype(float)
            df = df.sort_values('time').reset_index(drop=True)
            return df
    else:
        try:
            ticker = yf.Ticker(symbol)
            if timeframe == '4H':
                df = ticker.history(interval='1h', period='1mo')
            else:
                df = ticker.history(interval='5m', period='5d')
                
            if df.empty:
                return pd.DataFrame()
                
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            
            # Map datetime or date to time
            time_col = 'datetime' if 'datetime' in df.columns else 'date'
            df = df.rename(columns={time_col: 'time'})
            
            # Remove timezone awareness so it aligns perfectly with kucoin timestamps
            df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None)
            
            if timeframe == '4H':
                # Resample 1h into 4h blocks
                df = df.set_index('time')
                df = df.resample('4h').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna().reset_index()
                
            return df[['time', 'open', 'close', 'high', 'low', 'volume']]
        except Exception as e:
            print(f"Failed to fetch {symbol} via yfinance: {e}")
            
    return pd.DataFrame()

# --- SMC Algorithms ---
def get_pivots(df, window=3):
    highs = df['high'].values
    lows = df['low'].values
    pivot_highs = []
    pivot_lows = []
    
    for i in range(window, len(df) - window):
        is_sh = True
        for j in range(1, window + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_sh = False
                break
        if is_sh:
            pivot_highs.append({'index': i, 'time': df.iloc[i]['time'], 'price': highs[i]})
            
        is_sl = True
        for j in range(1, window + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_sl = False
                break
        if is_sl:
            pivot_lows.append({'index': i, 'time': df.iloc[i]['time'], 'price': lows[i]})
            
    return pivot_highs, pivot_lows

def get_htf_bias(df_4h):
    if df_4h.empty or len(df_4h) < 20:
        return "Unknown"
        
    ph, pl = get_pivots(df_4h, window=2)
    if len(ph) < 2 or len(pl) < 2:
        return "Neutral"
        
    last_h1, last_h2 = ph[-2]['price'], ph[-1]['price']
    last_l1, last_l2 = pl[-2]['price'], pl[-1]['price']
    
    if last_h2 > last_h1 and last_l2 > last_l1: return "Bullish"
    if last_h2 < last_h1 and last_l2 < last_l1: return "Bearish"
    return "Neutral"

def check_ltf_setup(df_5m, bias, risk_modifier="NORMAL", sentiment=None):
    if df_5m.empty or bias not in ["Bullish", "Bearish"]:
        return None
        
    ai_config = {}
    if os.path.exists("ai_strategy_config.json"):
        try:
            with open("ai_strategy_config.json", "r") as f:
                ai_config = json.load(f)
        except:
            pass
            
    whipsaw_pct = ai_config.get("whipsaw_buffer_pct", 0.2) / 100.0
    allowed_dir = ai_config.get("allowed_direction", "BOTH")
    base_rr = ai_config.get("base_rr_multiplier", 2)
    
    if allowed_dir == "SHORT_ONLY" and bias == "Bullish": return None
    if allowed_dir == "LONG_ONLY" and bias == "Bearish": return None
        
    ph, pl = get_pivots(df_5m, window=3) # 3-candle window for 5m pivots
    if not ph or not pl:
        return None

    last_swing_low = pl[-1]['price']
    last_swing_high = ph[-1]['price']
    
    recent_candles_index = max(pl[-1]['index'], ph[-1]['index']) + 1
    recent_candles = df_5m.iloc[recent_candles_index:]
    
    sweep_price = None
    ls_ratio = sentiment['ratio'] if sentiment else 1.0
    
    if bias == "Bullish":
        # 1. Fading the Crowd (Reject Longs if retail is excessively Long)
        if ls_ratio > 2.0:
            return None
            
        for _, candle in recent_candles.iterrows():
            if candle['low'] < last_swing_low and candle['close'] > last_swing_low:
                sweep_price = candle['low'] # This is the absolute bottom of the sweep
            
            if sweep_price and candle['close'] > last_swing_high:
                entry = candle['close']
                
                # 4. Whipsaw Protection (Dynamic SL)
                sl = sweep_price * (1.0 - whipsaw_pct) if risk_modifier == "REDUCED" else sweep_price
                
                risk = entry - sl
                if risk <= 0: return None
                
                # 3. A+ Setup Detection (Dynamic TP)
                rr_multiplier = base_rr + 1 if ls_ratio < 0.5 else base_rr
                tp = entry + (risk * rr_multiplier)
                
                direction_str = "LONG ⭐ A+ SETUP ⭐" if rr_multiplier == 3 else "LONG"
                
                return {"direction": direction_str, "entry": entry, "sl": sl, "tp": tp, "time": str(candle['time'])}
                
    elif bias == "Bearish":
        # 1. Fading the Crowd (Reject Shorts if retail is excessively Short)
        if ls_ratio < 0.5:
            return None
            
        for _, candle in recent_candles.iterrows():
            if candle['high'] > last_swing_high and candle['close'] < last_swing_high:
                sweep_price = candle['high'] # This is the absolute top of the sweep
                
            if sweep_price and candle['close'] < last_swing_low:
                entry = candle['close']
                
                # 4. Whipsaw Protection (Dynamic SL)
                sl = sweep_price * (1.0 + whipsaw_pct) if risk_modifier == "REDUCED" else sweep_price
                
                risk = sl - entry
                if risk <= 0: return None
                
                # 3. A+ Setup Detection (Dynamic TP)
                rr_multiplier = base_rr + 1 if ls_ratio > 2.0 else base_rr
                tp = entry - (risk * rr_multiplier)
                
                direction_str = "SHORT ⭐ A+ SETUP ⭐" if rr_multiplier == 3 else "SHORT"
                
                return {"direction": direction_str, "entry": entry, "sl": sl, "tp": tp, "time": str(candle['time'])}
                
    return None

# --- Scheduler & Main Runner ---
def run_bot(risk_modifier="NORMAL", sentiment=None):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking SMC structure on 5m... (Risk: {risk_modifier})")
    state = load_state()
    
    for symbol in TARGET_SYMBOLS:
        df_4h = fetch_candles(symbol, '4H')
        df_5m = fetch_candles(symbol, '5m')
        
        if df_4h.empty or df_5m.empty:
            print(f"Failed to fetch data for {symbol}")
            continue
            
        bias = get_htf_bias(df_4h)
        setup = check_ltf_setup(df_5m, bias, risk_modifier, sentiment)
        
        if setup:
            setup_id = f"{symbol}_{setup['direction']}_{setup['time']}"
            
            if state.get(symbol) != setup_id:
                risk_warning = "\n⚠️ **REDUCE POSITION SIZE BY 50% (NEWS DAY)**" if risk_modifier == "REDUCED" else ""
                
                # Extract RR multiplier from the direction string (A+ setups are 1:3)
                rr_str = "1:3 RR" if "A+ SETUP" in setup['direction'] else "1:2 RR"
                
                msg = (f"🚨 **SMC Trade Alert: {symbol}** 🚨\n"
                       f"Direction: **{setup['direction']}**\n"
                       f"Entry: ${setup['entry']:,.2f}\n"
                       f"Stop Loss: ${setup['sl']:,.2f}\n"
                       f"Take Profit: ${setup['tp']:,.2f} ({rr_str})\n"
                       f"HTF Bias: {bias}{risk_warning}")
                send_discord_alert(msg)
                
                state[symbol] = setup_id
                save_state(state)
            else:
                print(f"{symbol} - Setup already alerted.")
        else:
            print(f"{symbol} - No setup found.")

from macro_research import generate_daily_context

def start_scheduler():
    # Set your Killzones here (Local System Time - 24H format)
    # Since you are in GMT+5:
    # London Killzone: 12:00 PM to 2:00 PM
    # New York Killzone: 5:00 PM to 7:00 PM
    KILLZONES = [
        (12, 14), # London
        (17, 19)  # New York
    ]
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SMC Bot Started.")
    print("Sleeping until your scheduled Killzones (Local Time):")
    for start, end in KILLZONES:
        print(f"  - {start}:00 to {end}:00")
        
    last_macro_date = {} # Track so we don't spam the context report
    last_night_shift_date = ""
    current_risk_modifier = "NORMAL"
    current_sentiment = None
    
    while True:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # 1. Pre-Market Check (30 mins before Killzone)
        for start, end in KILLZONES:
            pre_market_time = start - 1 if start > 0 else 23
            
            if now.hour == pre_market_time and now.minute >= 30:
                if last_macro_date.get(start) != today_str:
                    print(f"[{now.strftime('%H:%M:%S')}] Running Pre-Market Macro Research...")
                    report, risk_modifier, sentiment = generate_daily_context()
                    current_risk_modifier = risk_modifier
                    current_sentiment = sentiment
                    
                    # Send to Discord
                    send_discord_alert(report)
                    
                    last_macro_date[start] = today_str
        
        # 2. Night Shift AI Trigger (Runs at 20:00 PM Local Time)
        if now.hour == 20 and now.minute == 0:
            if last_night_shift_date != today_str:
                print(f"[{now.strftime('%H:%M:%S')}] Spawning Deep Researcher Background Process...")
                import subprocess
                subprocess.Popen(["python", "deep_researcher.py"])
                last_night_shift_date = today_str
                
        # 3. Check if we are inside any of the killzone windows
        in_killzone = any(start <= now.hour < end for start, end in KILLZONES)
        
        if in_killzone:
            # Run the check exactly on the 5-minute marks (e.g. :00, :05, :10)
            if now.minute % 5 == 0:
                run_bot(current_risk_modifier, current_sentiment)
                # Sleep for 60 seconds to prevent running twice in the same minute
                time.sleep(60)
            else:
                # Wait until the next 5-minute mark
                time.sleep(10)
        else:
            # Outside killzones, sleep for a minute before checking time again
            time.sleep(60)

if __name__ == "__main__":
    # If you want to test it once immediately when you start it, uncomment the line below:
    # run_bot() 
    start_scheduler()
