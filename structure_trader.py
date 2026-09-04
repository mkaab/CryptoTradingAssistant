import streamlit as st
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time

# --- Config & Setup ---
BASE_URL = "https://api.kucoin.com"
TARGET_SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "EURUSD=X", "GBPUSD=X", "GC=F"]

st.set_page_config(layout="wide", page_title="SMC Crypto Screener")

# --- Helper Functions ---
@st.cache_data(ttl=60)
def make_request(url, max_retries=3, delay=1):
    """Fetch data from KuCoin API with retries."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        time.sleep(delay)
    return None

@st.cache_data(ttl=60)
def fetch_candles(symbol, timeframe):
    """Fetch OHLC data for a given symbol and timeframe."""
    if "-USDT" in symbol:
        if timeframe == '4H':
            interval = '4hour'
        elif timeframe == '1H':
            interval = '1hour'
        elif timeframe == '5m':
            interval = '5min'
        else:
            interval = '5min'
            
        url = f"{BASE_URL}/api/v1/market/candles?type={interval}&symbol={symbol}"
        data = make_request(url)
        
        if data and 'data' in data:
            # KuCoin format: [time, open, close, high, low, volume, turnover]
            # It's sorted descending by time (newest first).
            df = pd.DataFrame(data['data'], columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            df['time'] = pd.to_datetime(df['time'].astype(int), unit='s')
            for col in ['open', 'close', 'high', 'low', 'volume']:
                df[col] = df[col].astype(float)
            # Sort ascending (oldest to newest) for easier calculation
            df = df.sort_values('time').reset_index(drop=True)
            return df
    else:
        try:
            ticker = yf.Ticker(symbol)
            if timeframe == '4H':
                df = ticker.history(interval='1h', period='1mo')
            elif timeframe == '1H':
                df = ticker.history(interval='1h', period='2wk')
            else:
                df = ticker.history(interval='5m', period='5d')
                
            if df.empty:
                return pd.DataFrame()
                
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            
            time_col = 'datetime' if 'datetime' in df.columns else 'date'
            df = df.rename(columns={time_col: 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None)
            
            if timeframe == '4H':
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
            st.error(f"Failed to fetch {symbol} via yfinance: {e}")
            
    return pd.DataFrame()

# --- SMC Algorithms ---
def get_pivots(df, window=3):
    """
    Find Swing Highs and Swing Lows (Fractals).
    A Swing High is the highest high within +/- 'window' candles.
    A Swing Low is the lowest low within +/- 'window' candles.
    """
    highs = df['high'].values
    lows = df['low'].values
    
    pivot_highs = []
    pivot_lows = []
    
    # We leave 'window' candles buffer at the end so we don't confirm a pivot too early
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
    """
    Determine HTF Bias (Bullish, Bearish, or Neutral) based on recent 4H market structure.
    Checks the last 2 Swing Highs and last 2 Swing Lows.
    """
    if df_4h.empty or len(df_4h) < 20:
        return "Unknown"
        
    ph, pl = get_pivots(df_4h, window=2) # Slightly tighter window for 4H
    
    if len(ph) < 2 or len(pl) < 2:
        return "Neutral (Not enough data)"
        
    last_h1 = ph[-2]['price']
    last_h2 = ph[-1]['price']
    
    last_l1 = pl[-2]['price']
    last_l2 = pl[-1]['price']
    
    current_close = df_4h.iloc[-1]['close']
    
    # Bullish: Higher Highs and Higher Lows
    if last_h2 > last_h1 and last_l2 > last_l1:
        if current_close < last_l2:
            return "⚪ Neutral"
        return "🟢 Bullish"
    # Bearish: Lower Highs and Lower Lows
    elif last_h2 < last_h1 and last_l2 < last_l1:
        if current_close > last_h2:
            return "⚪ Neutral"
        return "🔴 Bearish"
    else:
        # E.g., Lower High but Higher Low (Consolidation/Triangle)
        return "⚪ Neutral"

def check_ltf_setup(df_5m, bias):
    """
    Check for Liquidity Sweeps and Break of Structure on the 5m chart.
    """
    if df_5m.empty or bias == "Unknown" or bias == "⚪ Neutral":
        return "No Setup", False, False
        
    ph, pl = get_pivots(df_5m, window=3)
    if not ph or not pl:
        return "Analyzing Data...", False, False

    last_swing_low = pl[-1]['price']
    last_swing_high = ph[-1]['price']
    
    # Look at the most recent candles (after the last confirmed pivot)
    recent_candles_index = max(pl[-1]['index'], ph[-1]['index']) + 1
    recent_candles = df_5m.iloc[recent_candles_index:]
    
    sweep_price = None
    internal_high = None
    internal_low = None
    sweep = False
    bos = False
    
    if "Bullish" in bias:
        # Bullish Setup: Sweep last swing low, then micro-BoS above sweep candle high
        for _, candle in recent_candles.iterrows():
            if candle['low'] < last_swing_low:
                sweep = True
                if not sweep_price or candle['low'] < sweep_price:
                    sweep_price = candle['low']
                    internal_high = candle['high']
            
            # Micro-BoS
            if sweep_price and candle['close'] > internal_high:
                bos = True
                
        if sweep and bos:
            return "🔥 LONG Confirmed", True, True
        elif sweep:
            return "👀 Sweep Detected (Wait for micro-BoS)", True, False
            
    elif "Bearish" in bias:
        # Bearish Setup: Sweep last swing high, then micro-BoS below sweep candle low
        for _, candle in recent_candles.iterrows():
            if candle['high'] > last_swing_high:
                sweep = True
                if not sweep_price or candle['high'] > sweep_price:
                    sweep_price = candle['high']
                    internal_low = candle['low']
                
            # Micro-BoS
            if sweep_price and candle['close'] < internal_low:
                bos = True
                
        if sweep and bos:
            return "🩸 SHORT Confirmed", True, True
        elif sweep:
            return "👀 Sweep Detected (Wait for micro-BoS)", True, False
            
    return "Waiting...", False, False


from macro_research import generate_daily_context

# --- Main Dashboard ---
def main():
    st.title("🏦 Smart Money Concepts (SMC) Screener")
    st.markdown("""
    **Methodology:**
    1. **Establish Bias (4H):** Detects if we are printing Higher Highs/Lows (Bullish) or Lower Highs/Lows (Bearish).
    2. **Avoid the 'BS' (5m Sweep):** Waits for market makers to hunt stop losses. A candle wicks past a recent structural point, but closes back inside.
    3. **Confirmation (5m BoS):** Enters only when a candle closes past the opposing structural point, confirming the reversal.
    """)
    
    st.markdown("---")
    
    # --- Macro Context Section ---
    with st.spinner("Fetching Macroeconomic Context..."):
        macro_report, risk_modifier = generate_daily_context()
        
    if risk_modifier == "REDUCED":
        st.warning(f"⚠️ **Macro Risk Warning:** High Impact News Today. Position sizes should be reduced. (Risk: {risk_modifier})")
    else:
        st.info(f"✅ **Macro Risk Status:** {risk_modifier}")
        
    with st.expander("View Full Daily Macro & Sentiment Report"):
        st.markdown(macro_report)
        
    st.markdown("---")
    
    results = []
    
    with st.spinner("Analyzing market structure across major pairs..."):
        for symbol in TARGET_SYMBOLS:
            # Fetch Data
            df_4h = fetch_candles(symbol, '4H')
            df_1h = fetch_candles(symbol, '1H')
            df_5m = fetch_candles(symbol, '5m')
            
            if df_4h.empty or df_1h.empty or df_5m.empty:
                st.warning(f"Failed to fetch data for {symbol}")
                continue
                
            bias_4h = get_htf_bias(df_4h)
            bias_1h = get_htf_bias(df_1h)
            
            # 3-Timeframe Alignment
            if "Bullish" in bias_4h and "Bearish" not in bias_1h:
                bias = "🟢 Bullish (Aligned)"
            elif "Bearish" in bias_4h and "Bullish" not in bias_1h:
                bias = "🔴 Bearish (Aligned)"
            else:
                bias = "⚪ Neutral / Unaligned"
                
            current_price = df_5m.iloc[-1]['close']
            
            status, has_sweep, has_bos = check_ltf_setup(df_5m, bias)
            
            # Append Results
            results.append({
                "Asset": symbol.replace('-USDT', ''),
                "Price": f"${current_price:,.2f}",
                "HTF Bias (4H->1H)": bias,
                "Sweep Detected (5m)": "✅ Yes" if has_sweep else "❌ No",
                "BoS Detected (5m)": "✅ Yes" if has_bos else "❌ No",
                "Action": status
            })

    if results:
        results_df = pd.DataFrame(results)
        st.dataframe(
            results_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Action": st.column_config.TextColumn("Signal Status")
            }
        )
    else:
        st.warning("Failed to fetch market data. KuCoin API might be rate-limiting.")
        
    st.caption(f"Last Refreshed: {datetime.now().strftime('%H:%M:%S UTC')} | Data Source: KuCoin Futures")

if __name__ == "__main__":
    main()
