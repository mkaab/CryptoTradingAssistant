import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime
import os

DB_FILE = "market_data.db"
TARGET_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "GC=F", "DX-Y.NYB"]
INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Create tables for each interval
    for interval in INTERVALS:
        table_name = f"ohlcv_{interval}"
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                symbol TEXT,
                time TIMESTAMP,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (symbol, time)
            )
        ''')
    conn.commit()
    conn.close()

def fetch_and_store_data(symbol, interval, period="30d"):
    """
    Downloads data from yfinance and upserts it into the SQLite database.
    """
    try:
        # 1m data is only available for the last 7 days on Yahoo Finance
        if interval == "1m" and period not in ["1d", "5d", "7d"]:
            period = "7d"
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, period=period)
        
        if df.empty:
            print(f"⚠️ No data fetched for {symbol} ({interval})")
            return
            
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        
        time_col = 'datetime' if 'datetime' in df.columns else 'date'
        df = df.rename(columns={time_col: 'time'})
        
        # Ensure time is timezone naive for sqlite and convert to string
        df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        df['symbol'] = symbol
        
        # Keep only required columns
        columns_to_keep = ['symbol', 'time', 'open', 'high', 'low', 'close', 'volume']
        df = df[columns_to_keep]
        
        # Upsert into database (INSERT OR REPLACE)
        conn = get_db_connection()
        table_name = f"ohlcv_{interval}"
        
        # Pandas to_sql doesn't support ON CONFLICT, so we write a manual executemany
        data = df.to_dict('records')
        c = conn.cursor()
        
        c.executemany(f'''
            INSERT OR REPLACE INTO {table_name} (symbol, time, open, high, low, close, volume)
            VALUES (:symbol, :time, :open, :high, :low, :close, :volume)
        ''', data)
        
        conn.commit()
        conn.close()
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
            conn = get_db_connection()
            c = conn.cursor()
            table_name = f"ohlcv_{interval}"
            c.execute(f"SELECT COUNT(*) FROM {table_name} WHERE symbol=?", (symbol,))
            count = c.fetchone()[0]
            conn.close()
            
            # If empty, do a bulk 30d fetch (or 7d for 1m). If it has data, just fetch the last 5 days incrementally.
            fetch_period = "30d" if count == 0 else "5d"
            fetch_and_store_data(symbol, interval, period=fetch_period)
            
def get_historical_data(symbol, interval, days=30):
    """
    Reads data directly from the local SQLite database. Extremely fast.
    """
    conn = get_db_connection()
    table_name = f"ohlcv_{interval}"
    
    # Calculate cutoff date
    cutoff = datetime.now() - pd.Timedelta(days=days)
    
    query = f"SELECT * FROM {table_name} WHERE symbol=? AND time >= ? ORDER BY time ASC"
    df = pd.read_sql_query(query, conn, params=(symbol, cutoff))
    conn.close()
    
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
        conn = get_db_connection()
        dfs = []
        for symbol in TARGET_SYMBOLS:
            query = "SELECT time, close FROM ohlcv_1d WHERE symbol=? ORDER BY time DESC LIMIT ?"
            df = pd.read_sql_query(query, conn, params=(symbol, days))
            if not df.empty:
                df = df.rename(columns={'close': symbol})
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                dfs.append(df)
        conn.close()
        
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
