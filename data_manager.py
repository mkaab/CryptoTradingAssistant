import pandas as pd
from datetime import datetime
import os
import ccxt
from twelvedata import TDClient
import time
from sqlalchemy import text
from db import get_engine

TARGET_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "GC=F", "DX-Y.NYB"]
INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]

def init_db():
    engine = get_engine()
    with engine.begin() as conn:
        for interval in INTERVALS:
            table_name = f"ohlcv_{interval}"
            conn.execute(text(f'''
                CREATE TABLE IF NOT EXISTS {table_name} (
                    symbol VARCHAR(50),
                    time TIMESTAMP,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    PRIMARY KEY (symbol, time)
                )
            '''))

def fetch_and_store_data(symbol, interval, period="30d"):
    """
    Downloads data from ccxt (Crypto) or TwelveData (Macro) and upserts it.
    """
    try:
        if symbol in ["BTC-USD", "ETH-USD", "SOL-USD"]:
            # Crypto -> CCXT (Kucoin)
            exchange = ccxt.kucoin({'enableRateLimit': True})
            ccxt_symbol = symbol.replace("-USD", "/USDT")
            
            # Map interval to KuCoin
            limit = 1500
            
            ohlcv = exchange.fetch_ohlcv(ccxt_symbol, interval, limit=limit)
            if not ohlcv:
                print(f"⚠️ No data fetched for {symbol} ({interval})")
                return
                
            df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['time'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')
            
        else:
            # Macro -> TwelveData
            td_key = os.getenv("TWELVEDATA_API_KEY")
            if not td_key:
                print(f"⚠️ TWELVEDATA_API_KEY is missing. Cannot fetch {symbol}.")
                return
                
            td = TDClient(apikey=td_key)
            td_symbol = "XAU/USD" if symbol == "GC=F" else "DXY"
            
            # Map intervals for TwelveData
            td_intervals = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1day"}
            td_interval = td_intervals.get(interval, "1h")
            
            ts = td.time_series(symbol=td_symbol, interval=td_interval, outputsize=1500)
            df = ts.as_pandas()
            
            if df is None or df.empty:
                print(f"⚠️ No data fetched for {symbol} ({interval})")
                return
                
            df = df.reset_index()
            df = df.rename(columns={'datetime': 'time'})
            df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # TwelveData doesn't always have volume for index/commodities, ensure it exists
            if 'volume' not in df.columns:
                df['volume'] = 0.0
                
        # Ensure correct column order
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        df['symbol'] = symbol
        
        # Keep only required columns
        columns_to_keep = ['symbol', 'time', 'open', 'high', 'low', 'close', 'volume']
        df = df[columns_to_keep]
        
        # Upsert into database (INSERT OR REPLACE)
        # Upsert into database
        engine = get_engine()
        table_name = f"ohlcv_{interval}"
        
        min_time = df['time'].min()
        max_time = df['time'].max()
        
        # Delete overlapping timeframe to prevent Primary Key violations, then insert
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table_name} WHERE symbol = :symbol AND time >= :min_time AND time <= :max_time"),
                         {"symbol": symbol, "min_time": min_time, "max_time": max_time})
                         
        df.to_sql(table_name, engine, if_exists='append', index=False)
        print(f"Synced {len(df)} candles for {symbol} ({interval}) to DB.")
        
    except Exception as e:
        print(f"Failed to sync {symbol} ({interval}): {e}")

def update_all_data():
    """
    Called by the Night Shift to incrementally update all data.
    Uses a 5-day period so it overlaps and catches missing candles, 
    but relies on SQLite's UPSERT to prevent duplicates.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Syncing Market Data to Local Database...")
    init_db()
    for symbol in TARGET_SYMBOLS:
        for interval in INTERVALS:
            # Check if we have data for this symbol/interval
            # Check if we have data for this symbol/interval
            engine = get_engine()
            table_name = f"ohlcv_{interval}"
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name} WHERE symbol=:symbol"), {"symbol": symbol})
                count = result.scalar()
            
            # If empty, do a bulk 30d fetch (or 7d for 1m). If it has data, just fetch the last 5 days incrementally.
            fetch_period = "30d" if count == 0 else "5d"
            fetch_and_store_data(symbol, interval, period=fetch_period)
            
def get_historical_data(symbol, interval, days=30):
    """
    Reads data directly from the local SQLite database. Extremely fast.
    """
    engine = get_engine()
    table_name = f"ohlcv_{interval}"
    
    # Calculate cutoff date
    cutoff = datetime.now() - pd.Timedelta(days=days)
    
    query = text(f"SELECT * FROM {table_name} WHERE symbol = :symbol AND time >= :cutoff ORDER BY time ASC")
    df = pd.read_sql_query(query, engine, params={"symbol": symbol, "cutoff": str(cutoff)})
    
    if not df.empty:
        df['time'] = pd.to_datetime(df['time'])
        
    return df

def calculate_correlation_matrix(days=30):
    """
    Calculates the Pearson correlation coefficient matrix between all TARGET_SYMBOLS
    over the last N days using 1d closing prices.
    Returns a formatted markdown string of the correlation matrix to feed to the CIO.
    """
    try:
        engine = get_engine()
        dfs = []
        for symbol in TARGET_SYMBOLS:
            query = text(f"SELECT time, close FROM ohlcv_1d WHERE symbol = :symbol ORDER BY time DESC LIMIT :lim")
            df = pd.read_sql_query(query, engine, params={"symbol": symbol, "lim": days})
            if not df.empty:
                df = df.rename(columns={'close': symbol})
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                dfs.append(df)
        
        if not dfs:
            return "No data available for correlation matrix."
            
        # Merge all dataframes on time
        merged_df = dfs[0]
        for i in range(1, len(dfs)):
            merged_df = merged_df.join(dfs[i], how='inner')
            
        # Calculate Pearson correlation
        corr_matrix = merged_df.corr(method='pearson')
        
        # Format as string
        report = "### 30-Day Pearson Correlation Matrix (Mathematical Precedence)\n"
        report += "*(1.0 = Perfect positive correlation, -1.0 = Perfect inverse correlation)*\n\n"
        report += corr_matrix.round(3).to_string()
        return report
        
    except Exception as e:
        return f"Error calculating correlation matrix: {e}"

if __name__ == "__main__":
    print("Initializing Database and running first sync...")
    update_all_data()
