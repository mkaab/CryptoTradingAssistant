import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time

# KuCoin API base URL
BASE_URL = "https://api.kucoin.com"

# Retry function for API calls
def make_request(url, max_retries=3, delay=2):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.json()
            else:
                st.warning(f"API returned status {response.status_code} on attempt {attempt + 1}")
        except requests.exceptions.Timeout:
            st.warning(f"Timeout on attempt {attempt + 1}")
        except Exception as e:
            st.warning(f"Request error on attempt {attempt + 1}: {e}")
        if attempt < max_retries - 1:
            time.sleep(delay)
    st.error(f"Failed to fetch data from {url}")
    return None

# RSI calculation
def calculate_rsi(closes, period=14):
    if len(closes) < period:
        return np.nan
    delta = pd.Series(closes).diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else np.nan

# EMA calculation
def calculate_ema(closes, period=20):
    if len(closes) < period:
        return np.nan
    multiplier = 2 / (period + 1)
    ema = np.zeros(len(closes))
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = (closes[i] * multiplier) + (ema[i-1] * (1 - multiplier))
    return ema[-1]

# MACD calculation
def calculate_macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow:
        return np.nan, np.nan, np.nan
    ema_fast = pd.Series(closes).ewm(span=fast, adjust=False).mean()
    ema_slow = pd.Series(closes).ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

# ATR calculation
def calculate_atr(highs, lows, closes, period=14):
    if len(highs) < period:
        return np.nan
    tr_list = []
    for i in range(len(highs)):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - (closes[i-1] if i > 0 else closes[i]))
        low_prev_close = abs(lows[i] - (closes[i-1] if i > 0 else closes[i]))
        tr = max(high_low, high_prev_close, low_prev_close)
        tr_list.append(tr)
    atr = pd.Series(tr_list).rolling(window=period).mean().iloc[-1]
    return atr

# Bollinger Bands calculation
def calculate_bb(closes, period=20, std_dev=2):
    if len(closes) < period:
        return np.nan, np.nan, np.nan
    sma = pd.Series(closes).rolling(window=period).mean().iloc[-1]
    std = pd.Series(closes).rolling(window=period).std().iloc[-1]
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    width = (upper - lower) / sma * 100  # As percentage
    return upper, lower, width

# Signal Scoring and Probability
def calculate_probability(row):
    score = 0
    price = float(row['current_price'].replace('$', '')) if isinstance(row['current_price'], str) and row['current_price'] != "$0.00" else 0.0
    if pd.notna(row['rsi']) and (row['rsi'] < 40 or row['rsi'] > 70): score += 25
    if pd.notna(row['macd']) and pd.notna(row['macd_signal']) and (row['macd'] > row['macd_signal'] or row['macd'] < row['macd_signal']): score += 25
    if pd.notna(row['ema_20']) and (price > row['ema_20'] or price < row['ema_20']): score += 25
    if pd.notna(row['macd_hist']) and row['macd_hist'] != 0: score += 25
    return 'High' if score >= 75 else 'Medium' if score >= 50 else 'Low'

# Fetch top 10 cryptos
@st.cache_data(ttl=60)
def fetch_top_10():
    try:
        # Get all tickers
        tickers_data = make_request(f"{BASE_URL}/api/v1/market/allTickers")
        if not tickers_data or 'data' not in tickers_data or 'ticker' not in tickers_data['data']:
            st.error("Invalid ticker data from KuCoin API")
            return pd.DataFrame()
        
        tickers = tickers_data['data']['ticker']
        usdt_pairs = [t for t in tickers if t.get('symbol', '').endswith('-USDT') and pd.notna(t.get('volValue')) and pd.notna(t.get('last'))]
        if not usdt_pairs:
            st.error("No valid USDT pairs found")
            return pd.DataFrame()
        
        df = pd.DataFrame(usdt_pairs)
        df['volume_usd'] = df['volValue'].astype(float, errors='ignore')
        df['price'] = df['last'].astype(float, errors='ignore')
        df['market_cap_approx'] = df['volume_usd'] * df['price']
        top_symbols = ['BTC-USDT', 'ETH-USDT', 'USDT-USDT', 'BNB-USDT', 'SOL-USDT', 'XRP-USDT', 'USDC-USDT', 'DOGE-USDT', 'STETH-USDT', 'TRX-USDT']
        df = df[df['symbol'].isin(top_symbols)].sort_values('market_cap_approx', ascending=False)
        df = df.head(10).reset_index(drop=True)
        
        # Pad to 10 rows if needed
        if len(df) < 10:
            missing = 10 - len(df)
            missing_df = pd.DataFrame({
                'symbol': ['UNKNOWN-USDT'] * missing,
                'volValue': [0.0] * missing,
                'last': [0.0] * missing,
                'changeRate': [0.0] * missing,
                'volume_usd': [0.0] * missing,
                'price': [0.0] * missing,
                'market_cap_approx': [0.0] * missing
            })
            df = pd.concat([df, missing_df], ignore_index=True)
        
        # Initialize output DataFrame
        result = pd.DataFrame({
            'name': df['symbol'].str.replace('-USDT', '').fillna('UNKNOWN'),
            'symbol': df['symbol'].str.replace('-USDT', '').str.lower().fillna('unknown'),
            'current_price': df['last'].astype(float).apply(lambda x: f"${x:.2f}" if x > 0 else "$0.00"),
            'market_cap': df['market_cap_approx'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "$0"),
            'price_change_percentage_24h': df['changeRate'].astype(float) * 100,
            'total_volume': df['volValue'].astype(float).apply(lambda x: f"${x:,.0f}" if x > 0 else "$0")
        })
        result['4h_high'] = np.nan
        result['4h_low'] = np.nan
        result['7d_high'] = np.nan
        result['7d_low'] = np.nan
        result['rsi'] = np.nan
        result['ema_20'] = np.nan
        result['macd'] = np.nan
        result['macd_signal'] = np.nan
        result['macd_hist'] = np.nan
        result['atr'] = np.nan
        result['30d_high'] = np.nan
        result['30d_low'] = np.nan
        result['bb_upper'] = np.nan
        result['bb_lower'] = np.nan
        result['bb_width'] = np.nan
        result['probability'] = 'Low'
        result = result.reset_index(drop=True)
        
        # Fetch OHLC data
        for i in range(len(result)):
            row = result.iloc[i]
            if row['symbol'] == 'unknown' or pd.isna(row['symbol']):
                st.warning(f"Skipping OHLC for invalid symbol at index {i}")
                continue
            symbol = f"{row['symbol'].upper()}-USDT"
            price = float(row['current_price'].replace('$', '')) if row['current_price'] != "$0.00" else 0.0
            
            # 4-hour OHLC
            ohlc_data = make_request(f"{BASE_URL}/api/v1/market/candles?type=4hour&symbol={symbol}")
            if ohlc_data and 'data' in ohlc_data:
                ohlc = ohlc_data.get('data', [])
                if ohlc and len(ohlc) > 20:  # Ensure enough data for BB/EMA
                    highs = [float(candle[3]) for candle in ohlc]
                    lows = [float(candle[4]) for candle in ohlc]
                    closes = [float(candle[2]) for candle in ohlc]
                    result.at[i, '4h_high'] = max(highs)
                    result.at[i, '4h_low'] = min(lows)
                    result.at[i, 'rsi'] = calculate_rsi(closes, 14)
                    result.at[i, 'ema_20'] = calculate_ema(closes, 20)
                    macd, signal, hist = calculate_macd(closes)
                    result.at[i, 'macd'] = macd
                    result.at[i, 'macd_signal'] = signal
                    result.at[i, 'macd_hist'] = hist
                    result.at[i, 'atr'] = calculate_atr(highs, lows, closes, 14)
                    upper, lower, width = calculate_bb(closes)
                    result.at[i, 'bb_upper'] = upper
                    result.at[i, 'bb_lower'] = lower
                    result.at[i, 'bb_width'] = width
                else:
                    st.warning(f"No 4h OHLC data for {row['name']}")
            else:
                st.warning(f"Failed to fetch 4h OHLC for {row['name']}")
            
            # Fallback for missing data
            result.at[i, '4h_high'] = price if pd.isna(result.at[i, '4h_high']) else result.at[i, '4h_high']
            result.at[i, '4h_low'] = price if pd.isna(result.at[i, '4h_low']) else result.at[i, '4h_low']
            
            # 7-day OHLC
            ohlc_7d_data = make_request(f"{BASE_URL}/api/v1/market/candles?type=1day&symbol={symbol}")
            if ohlc_7d_data and 'data' in ohlc_7d_data:
                ohlc_7d = ohlc_7d_data.get('data', [])
                if ohlc_7d:
                    highs = [float(candle[3]) for candle in ohlc_7d[:7]]
                    lows = [float(candle[4]) for candle in ohlc_7d[:7]]
                    result.at[i, '7d_high'] = max(highs)
                    result.at[i, '7d_low'] = min(lows)
                else:
                    st.warning(f"No 7d OHLC data for {row['name']}")
            else:
                st.warning(f"Failed to fetch 7d OHLC for {row['name']}")
            
            result.at[i, '7d_high'] = price if pd.isna(result.at[i, '7d_high']) else result.at[i, '7d_high']
            result.at[i, '7d_low'] = price if pd.isna(result.at[i, '7d_low']) else result.at[i, '7d_low']
            
            # 30-day OHLC
            ohlc_30d_data = make_request(f"{BASE_URL}/api/v1/market/candles?type=1day&symbol={symbol}")
            if ohlc_30d_data and 'data' in ohlc_30d_data:
                ohlc_30d = ohlc_30d_data.get('data', [])
                if ohlc_30d:
                    highs = [float(candle[3]) for candle in ohlc_30d[:30]]
                    lows = [float(candle[4]) for candle in ohlc_30d[:30]]
                    result.at[i, '30d_high'] = max(highs)
                    result.at[i, '30d_low'] = min(lows)
                else:
                    st.warning(f"No 30d OHLC data for {row['name']}")
            else:
                st.warning(f"Failed to fetch 30d OHLC for {row['name']}")
            
            result.at[i, '30d_high'] = price if pd.isna(result.at[i, '30d_high']) else result.at[i, '30d_high']
            result.at[i, '30d_low'] = price if pd.isna(result.at[i, '30d_low']) else result.at[i, '30d_low']
            
            # Calculate probability
            result.at[i, 'probability'] = calculate_probability(result.iloc[i])
        
        return result
    except Exception as e:
        st.error(f"Error fetching market data: {e}")
        return pd.DataFrame()

# Main Area: Screener
st.set_page_config(layout="wide")
st.title("🪙 Crypto Swing Trading Screener (Top 10 by Market Cap, KuCoin Futures)")

df = fetch_top_10()
if not df.empty:
    st.dataframe(
        df,
        column_config={
            "name": st.column_config.TextColumn("Name", width="medium"),
            "symbol": st.column_config.TextColumn("Symbol"),
            "current_price": st.column_config.TextColumn("Price (USD)"),
            "market_cap": st.column_config.TextColumn("Market Cap (Approx)"),
            "price_change_percentage_24h": st.column_config.NumberColumn("24h %", format="%.2f%"),
            "total_volume": st.column_config.TextColumn("Volume (USD)"),
            "4h_high": st.column_config.NumberColumn("4h High (USD)", format="$%.2f"),
            "4h_low": st.column_config.NumberColumn("4h Low (USD)", format="$%.2f"),
            "7d_high": st.column_config.NumberColumn("7d High (USD)", format="$%.2f"),
            "7d_low": st.column_config.NumberColumn("7d Low (USD)", format="$%.2f"),
            "rsi": st.column_config.NumberColumn("RSI (14)", format="%.2f"),
            "ema_20": st.column_config.NumberColumn("EMA (20, 4h)", format="$%.2f"),
            "macd": st.column_config.NumberColumn("MACD", format="%.2f"),
            "macd_signal": st.column_config.NumberColumn("MACD Signal", format="%.2f"),
            "macd_hist": st.column_config.NumberColumn("MACD Histogram", format="%.2f"),
            "atr": st.column_config.NumberColumn("ATR (14, 4h)", format="$%.2f"),
            "30d_high": st.column_config.NumberColumn("30d High (USD)", format="$%.2f"),
            "30d_low": st.column_config.NumberColumn("30d Low (USD)", format="$%.2f"),
            "bb_upper": st.column_config.NumberColumn("BB Upper (USD)", format="$%.2f"),
            "bb_lower": st.column_config.NumberColumn("BB Lower (USD)", format="$%.2f"),
            "bb_width": st.column_config.NumberColumn("BB Width (%)", format="%.2f%"),
            "probability": st.column_config.TextColumn("Probability")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Swing trading filters
    st.subheader("Swing Opportunities")
    swing_trends = df[df['price_change_percentage_24h'] > 2]
    if not swing_trends.empty:
        names = [str(name) for name in swing_trends['name'].tolist() if name != 'UNKNOWN']
        st.success(f"Strong Trends (24h >2%): {', '.join(names) if names else 'None'}")
        st.dataframe(
            swing_trends[['name', 'symbol', 'current_price', 'price_change_percentage_24h', '4h_high', '4h_low', 'rsi', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "price_change_percentage_24h": "24h %",
                "4h_high": "4h High (USD)",
                "4h_low": "4h Low (USD)",
                "rsi": "RSI (14)",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    
    near_4h_low = df[pd.notna(df['4h_low']) & (df['4h_low'] != 0) & ((df['current_price'].str.replace('$', '').astype(float) - df['4h_low']) / df['4h_low'] * 100 < 2)]
    if not near_4h_low.empty:
        names = [str(name) for name in near_4h_low['name'].tolist() if name != 'UNKNOWN']
        st.success(f"Near 4h Low (<2% from low): {', '.join(names) if names else 'None'}")
        st.dataframe(
            near_4h_low[['name', 'symbol', 'current_price', '4h_low', 'rsi', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "4h_low": "4h Low (USD)",
                "rsi": "RSI (14)",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    
    near_30d_high = df[pd.notna(df['30d_high']) & (df['30d_high'] != 0) & (df['current_price'].str.replace('$', '').astype(float) / df['30d_high'] > 0.98)]
    if not near_30d_high.empty:
        names = [str(name) for name in near_30d_high['name'].tolist() if name != 'UNKNOWN']
        st.success(f"Near 30d High (>98% of high): {', '.join(names) if names else 'None'}")
        st.dataframe(
            near_30d_high[['name', 'symbol', 'current_price', '30d_high', 'rsi', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "30d_high": "30d High (USD)",
                "rsi": "RSI (14)",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    
    rsi_low = df[df['rsi'] < 40]
    if not rsi_low.empty:
        names = [str(name) for name in rsi_low['name'].tolist() if name != 'UNKNOWN']
        st.success(f"Oversold (RSI < 40): {', '.join(names) if names else 'None'}")
        st.dataframe(
            rsi_low[['name', 'symbol', 'current_price', 'rsi', 'ema_20', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "rsi": "RSI (14)",
                "ema_20": "EMA (20, 4h)",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    
    rsi_high = df[df['rsi'] > 70]
    if not rsi_high.empty:
        names = [str(name) for name in rsi_high['name'].tolist() if name != 'UNKNOWN']
        st.success(f"Overbought (RSI > 70): {', '.join(names) if names else 'None'}")
        st.dataframe(
            rsi_high[['name', 'symbol', 'current_price', 'rsi', 'ema_20', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "rsi": "RSI (14)",
                "ema_20": "EMA (20, 4h)",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    
    macd_bullish = df[(df['macd'] > df['macd_signal']) & df['macd'].notna() & df['macd_signal'].notna()]
    if not macd_bullish.empty:
        names = [str(name) for name in macd_bullish['name'].tolist() if name != 'UNKNOWN']
        st.success(f"MACD Bullish (MACD > Signal): {', '.join(names) if names else 'None'}")
        st.dataframe(
            macd_bullish[['name', 'symbol', 'current_price', 'macd', 'macd_signal', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "macd": "MACD",
                "macd_signal": "MACD Signal",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    
    macd_bearish = df[(df['macd'] < df['macd_signal']) & df['macd'].notna() & df['macd_signal'].notna()]
    if not macd_bearish.empty:
        names = [str(name) for name in macd_bearish['name'].tolist() if name != 'UNKNOWN']
        st.success(f"MACD Bearish (MACD < Signal): {', '.join(names) if names else 'None'}")
        st.dataframe(
            macd_bearish[['name', 'symbol', 'current_price', 'macd', 'macd_signal', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "macd": "MACD",
                "macd_signal": "MACD Signal",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    
    high_prob = df[((df['rsi'] < 40) & (df['macd'] > df['macd_signal']) | (df['rsi'] > 70) & (df['macd'] < df['macd_signal'])) & df['rsi'].notna() & df['macd'].notna() & df['macd_signal'].notna()]
    if not high_prob.empty:
        names = [str(name) for name in high_prob['name'].tolist() if name != 'UNKNOWN']
        st.success(f"High Probability (RSI <40 & MACD Bullish or RSI >70 & MACD Bearish): {', '.join(names) if names else 'None'}")
        st.dataframe(
            high_prob[['name', 'symbol', 'current_price', 'rsi', 'macd_hist', 'atr', 'bb_width', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "rsi": "RSI (14)",
                "macd_hist": "MACD Histogram",
                "atr": "ATR (14, 4h)",
                "bb_width": "BB Width (%)",
                "probability": "Probability"
            }
        )
    else:
        st.info("No high-probability setups (RSI <40 & MACD Bullish or RSI >70 & MACD Bearish)—check back soon!")
    
    bb_squeeze = df[df['bb_width'] < 10]
    if not bb_squeeze.empty:
        names = [str(name) for name in bb_squeeze['name'].tolist() if name != 'UNKNOWN']
        st.success(f"BB Squeeze (Width < 10%): {', '.join(names) if names else 'None'}")
        st.dataframe(
            bb_squeeze[['name', 'symbol', 'current_price', 'bb_upper', 'bb_lower', 'bb_width', 'rsi', 'macd_hist', 'probability']],
            hide_index=True,
            column_config={
                "name": "Name",
                "symbol": "Symbol",
                "current_price": "Price (USD)",
                "bb_upper": "BB Upper (USD)",
                "bb_lower": "BB Lower (USD)",
                "bb_width": "BB Width (%)",
                "rsi": "RSI (14)",
                "macd_hist": "MACD Histogram",
                "probability": "Probability"
            }
        )
    
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Refreshes every 60s")
    
    # AI Prompt for Refinement
    st.subheader("AI Prompt for Swing Trading Advice")
    st.markdown("Refine this prompt to generate swing trading setups. Copy and modify for AI integration (e.g., via xAI API).")
    default_prompt = f"""Based on this top 10 crypto screener data (swing trading focus, KuCoin futures, 5x-20x leverage):
{df[df['name'] != 'UNKNOWN'].to_string(index=False)}

Quick Filters:
- Strong Trends (24h >2%): {[row['name'] for _, row in df.iterrows() if pd.notna(row['price_change_percentage_24h']) and row['price_change_percentage_24h'] > 2 and row['name'] != 'UNKNOWN'] or ['None']}
- High Volume (>$500M): {[row['name'] for _, row in df.iterrows() if float(row['total_volume'].replace('$', '').replace(',', '')) > 500_000_000 and row['name'] != 'UNKNOWN'] or ['None']}
- Near 4h Low (<2% from low): {[row['name'] for _, row in df.iterrows() if pd.notna(row['4h_low']) and row['4h_low'] != 0 and ((float(row['current_price'].replace('$', '')) - row['4h_low']) / row['4h_low'] * 100) < 2 and row['name'] != 'UNKNOWN'] or ['None']}
- Near 30d High (>98% of high): {[row['name'] for _, row in df.iterrows() if pd.notna(row['30d_high']) and row['30d_high'] != 0 and ((float(row['current_price'].replace('$', '')) / row['30d_high']) > 0.98) and row['name'] != 'UNKNOWN'] or ['None']}
- RSI < 40 (Oversold): {[row['name'] for _, row in df.iterrows() if pd.notna(row['rsi']) and row['rsi'] < 40 and row['name'] != 'UNKNOWN'] or ['None']}
- RSI > 70 (Overbought): {[row['name'] for _, row in df.iterrows() if pd.notna(row['rsi']) and row['rsi'] > 70 and row['name'] != 'UNKNOWN'] or ['None']}
- MACD Bullish (MACD > Signal): {[row['name'] for _, row in df.iterrows() if pd.notna(row['macd']) and pd.notna(row['macd_signal']) and row['macd'] > row['macd_signal'] and row['name'] != 'UNKNOWN'] or ['None']}
- MACD Bearish (MACD < Signal): {[row['name'] for _, row in df.iterrows() if pd.notna(row['macd']) and pd.notna(row['macd_signal']) and row['macd'] < row['macd_signal'] and row['name'] != 'UNKNOWN'] or ['None']}
- High Probability (RSI <40 & MACD Bullish or RSI >70 & MACD Bearish): {[row['name'] for _, row in df.iterrows() if pd.notna(row['rsi']) and ((row['rsi'] < 40 and pd.notna(row['macd']) and pd.notna(row['macd_signal']) and row['macd'] > row['macd_signal']) or (row['rsi'] > 70 and pd.notna(row['macd']) and pd.notna(row['macd_signal']) and row['macd'] < row['macd_signal'])) and row['name'] != 'UNKNOWN'] or ['None']}
- BB Squeeze (Width < 10%): {[row['name'] for _, row in df.iterrows() if pd.notna(row['bb_width']) and row['bb_width'] < 10 and row['name'] != 'UNKNOWN'] or ['None']}

Swing trading advice ({datetime.now().strftime('%Y-%m-%d %H:%M')}): Provide a swing trade setup for KuCoin futures with entry/exit, risk/reward (1:2 min), 5x-20x leverage, $100 trade size, and why it fits. Use ATR for dynamic target (entry ± 1.5x ATR) and stop (entry ± 1x ATR). Prioritize High probability setups; include Bollinger Bands context (price near upper/lower band, squeeze)."""
    st.text_area("Refine AI Prompt", value=default_prompt, height=400, key="ai_prompt")
    st.markdown("**Tip**: Modify the prompt (e.g., add specific pairs like 'BNB/USDT', adjust leverage, or request X sentiment) and test with an AI. For integration, use this string with an API call (e.g., xAI API at https://x.ai/api).")
else:
    st.warning("Unable to load data—check KuCoin API connection.")

# Footer
st.markdown("---")
st.caption("Manual trading only on KuCoin futures. Use at your own risk—always DYOR!")