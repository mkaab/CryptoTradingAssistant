import yfinance as yf
import pandas as pd
import numpy as np

# SMC Math (imported logic)
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
            pivot_highs.append({'index': i, 'price': highs[i]})
            
        is_sl = True
        for j in range(1, window + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_sl = False
                break
        if is_sl:
            pivot_lows.append({'index': i, 'price': lows[i]})
            
    return pivot_highs, pivot_lows

def get_htf_bias(df_4h_slice):
    if len(df_4h_slice) < 20:
        return "Unknown"
        
    ph, pl = get_pivots(df_4h_slice, window=2)
    if len(ph) < 2 or len(pl) < 2:
        return "Neutral"
        
    last_h1, last_h2 = ph[-2]['price'], ph[-1]['price']
    last_l1, last_l2 = pl[-2]['price'], pl[-1]['price']
    
    if last_h2 > last_h1 and last_l2 > last_l1: return "Bullish"
    if last_h2 < last_h1 and last_l2 < last_l1: return "Bearish"
    return "Neutral"

def backtest_smc(symbol="GC=F", days=30, interval="5m", htf_interval="4h"):
    print(f"Loading {days} days of data for {symbol} ({interval})...")
    
    # 1. Fetch Data from Local DB
    from data_manager import get_historical_data
    df_5m = get_historical_data(symbol, interval, days)
    if df_5m.empty:
        print(f"Failed to load {interval} data from DB.")
        return
    
    # 2. Resample for HTF Bias
    # Need to map pandas offset strings based on htf_interval
    resample_rule = '4h'
    if htf_interval == '1d': resample_rule = '1d'
    if htf_interval == '1wk': resample_rule = '1W'
        
    df_4h = df_5m.set_index('time').resample(resample_rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna().reset_index()
    
    print(f"Loaded {len(df_5m)} {interval} candles and {len(df_4h)} {htf_interval} candles.")
    print(f"Running Backtest Engine ({interval})...\n")
    
    trades = []
    capital = 1000.0
    risk_per_trade = 10.0 # Risking $10 per trade (1% of capital)
    
    # Define Killzones (using UTC hours roughly matching London/NY opens)
    KILLZONES = [(7, 10), (13, 16)]
    
    # We need at least 100 candles to establish a baseline
    for i in range(100, len(df_5m) - 1):
        current_time = df_5m.iloc[i]['time']
        
        # Slicing data up to current point in time
        df_5m_slice = df_5m.iloc[:i+1]
        df_4h_slice = df_4h[df_4h['time'] <= current_time]
        
        # Only take trades inside the Killzones
        in_killzone = any(start <= current_time.hour <= end for start, end in KILLZONES)
        if not in_killzone:
            continue
        
        bias = get_htf_bias(df_4h_slice)
        if bias not in ["Bullish", "Bearish"]:
            continue
            
        ph, pl = get_pivots(df_5m_slice, window=3)
        if not ph or not pl:
            continue
            
        last_swing_low = pl[-1]['price']
        last_swing_high = ph[-1]['price']
        
        # Check the last 15 candles for a sweep (Loosened logic)
        recent_index_start = max(0, i - 15)
        recent_candles = df_5m.iloc[recent_index_start:i+1]
        
        current_candle = df_5m.iloc[i]
        
        if bias == "Bullish":
            sweep_price = None
            for _, c in recent_candles.iterrows():
                if c['low'] < last_swing_low and c['close'] > last_swing_low:
                    sweep_price = c['low']
                    
            if sweep_price and current_candle['close'] > last_swing_high:
                # BoS confirmed! Enter Trade
                entry = current_candle['close']
                sl = sweep_price * 0.998 # Small buffer
                risk = entry - sl
                
                if risk <= 0: continue
                
                tp = entry + (risk * 2.5) # 1:2.5 Risk/Reward
                
                trades.append({
                    'time': current_time,
                    'direction': 'LONG',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'status': 'OPEN'
                })
                # Skip forward slightly so we don't double trigger
                i += 5 
                
        elif bias == "Bearish":
            sweep_price = None
            for _, c in recent_candles.iterrows():
                if c['high'] > last_swing_high and c['close'] < last_swing_high:
                    sweep_price = c['high']
                    
            if sweep_price and current_candle['close'] < last_swing_low:
                entry = current_candle['close']
                sl = sweep_price * 1.002
                risk = sl - entry
                
                if risk <= 0: continue
                
                tp = entry - (risk * 2.5)
                
                trades.append({
                    'time': current_time,
                    'direction': 'SHORT',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'status': 'OPEN'
                })
                i += 5
                
    # 3. Simulate Trade Outcomes
    print(f"Generated {len(trades)} signals. Simulating outcomes...")
    wins = 0
    losses = 0
    be_trades = 0
    
    for trade in trades:
        future_data = df_5m[df_5m['time'] > trade['time']]
        
        sl = trade['sl']
        risk = abs(trade['entry'] - sl)
        be_trigger = trade['entry'] + risk if trade['direction'] == 'LONG' else trade['entry'] - risk
        
        max_price = trade['entry']
        min_price = trade['entry']
        trade['exit_time'] = None
        trade['exit_price'] = None
        trade['pnl_percent'] = 0.0
        
        for _, candle in future_data.iterrows():
            if candle['high'] > max_price: max_price = candle['high']
            if candle['low'] < min_price: min_price = candle['low']
            
            if trade['direction'] == 'LONG':
                if candle['low'] <= sl:
                    trade['exit_time'] = candle['time']
                    trade['exit_price'] = sl
                    if sl == trade['entry']:
                        trade['status'] = 'BE'
                        be_trades += 1
                    else:
                        trade['status'] = 'LOSS'
                        losses += 1
                        capital -= risk_per_trade
                        trade['pnl_percent'] = ((sl - trade['entry'])/trade['entry']) * 100
                    break
                elif candle['high'] >= trade['tp']:
                    trade['exit_time'] = candle['time']
                    trade['exit_price'] = trade['tp']
                    trade['status'] = 'WIN'
                    wins += 1
                    capital += (risk_per_trade * 2.5)
                    trade['pnl_percent'] = ((trade['tp'] - trade['entry'])/trade['entry']) * 100
                    break
                    
                if candle['high'] >= be_trigger:
                    sl = trade['entry']
            else:
                if candle['high'] >= sl:
                    trade['exit_time'] = candle['time']
                    trade['exit_price'] = sl
                    if sl == trade['entry']:
                        trade['status'] = 'BE'
                        be_trades += 1
                    else:
                        trade['status'] = 'LOSS'
                        losses += 1
                        capital -= risk_per_trade
                        trade['pnl_percent'] = ((trade['entry'] - sl)/trade['entry']) * 100
                    break
                elif candle['low'] <= trade['tp']:
                    trade['exit_time'] = candle['time']
                    trade['exit_price'] = trade['tp']
                    trade['status'] = 'WIN'
                    wins += 1
                    capital += (risk_per_trade * 2.5)
                    trade['pnl_percent'] = ((trade['entry'] - trade['tp'])/trade['entry']) * 100
                    break
                    
                if candle['low'] <= be_trigger:
                    sl = trade['entry']
                    
        # Calculate MAE / MFE
        if trade['direction'] == 'LONG':
            trade['mae_percent'] = ((min_price - trade['entry'])/trade['entry'])*100
            trade['mfe_percent'] = ((max_price - trade['entry'])/trade['entry'])*100
        else:
            trade['mae_percent'] = ((trade['entry'] - max_price)/trade['entry'])*100
            trade['mfe_percent'] = ((trade['entry'] - min_price)/trade['entry'])*100
                    
    # 4. Save and Print Results
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pnl = capital - 1000.0
    
    report = f"# SMC Backtest Results ({symbol})\n\n"
    report += f"- **Strategy:** Smart Money Concepts (15-candle Sweep Window)\n"
    report += f"- **Interval:** {interval} (HTF Bias: {htf_interval})\n"
    report += f"- **Period:** Last {days} Days\n"
    report += f"- **Sessions:** London & NY Killzones Only\n"
    report += f"- **Initial Capital:** $1,000.00\n"
    report += f"- **Final Capital:** ${capital:,.2f}\n"
    report += f"- **Net PnL:** ${pnl:,.2f}\n"
    report += f"- **Total Trades:** {total_trades}\n"
    report += f"- **Win Rate:** {win_rate:.2f}%\n"
    report += f"- **Wins:** {wins} | **Losses:** {losses} | **Break-Even:** {be_trades}\n"
    report += f"- **Risk/Reward:** 1:2.5 (With 1:1 Trailing Stop)\n"
    
    from file_store import write_file
    write_file("backtest_results.md", report, mode="a")
        
    print(report)
    
    # Write to DB
    from db import get_engine
    engine = get_engine()
    db_trades = []
    for t in trades:
        if t['status'] != 'OPEN':
            db_trades.append({
                'strategy': 'SMC',
                'symbol': symbol,
                'direction': t['direction'],
                'entry_time': t['time'],
                'entry_price': t['entry'],
                'exit_time': t['exit_time'],
                'exit_price': t['exit_price'],
                'pnl_percent': t['pnl_percent'],
                'mae_percent': t['mae_percent'],
                'mfe_percent': t['mfe_percent'],
                'status': t['status']
            })
    if db_trades:
        pd.DataFrame(db_trades).to_sql('smc_backtests', engine, if_exists='append', index=False)

import ta

def backtest_rapid_fire(symbol="GC=F", days=30, interval="5m"):
    print(f"\n--- RAPID FIRE STRATEGY ({symbol} | {interval}) ---")
    from data_manager import get_historical_data
    df = get_historical_data(symbol, interval, days)
    if df.empty: return
    
    # Calculate Indicators
    psar_indicator = ta.trend.PSARIndicator(high=df['high'], low=df['low'], close=df['close'], step=0.02, max_step=0.2)
    df['psar'] = psar_indicator.psar()
    df['sma50'] = ta.trend.sma_indicator(df['close'], window=50)
    
    capital = 1000.0
    wins = 0
    losses = 0
    
    trades = []
    
    # 0.5% TP and 1.5% SL
    # Risk per trade is $10. Which corresponds to a 1.5% move.
    
    for i in range(50, len(df)):
        current = df.iloc[i]
        prev = df.iloc[i-1]
        
        # We need psar to not be NaN
        if pd.isna(current['psar']) or pd.isna(prev['psar']) or pd.isna(current['sma50']):
            continue
            
        longCondition = (current['open'] > current['psar']) and (prev['open'] < prev['psar']) and (current['open'] > current['sma50'])
        shortCondition = (current['open'] < current['psar']) and (prev['open'] > prev['psar']) and (current['open'] < current['sma50'])
        
        if longCondition:
            entry = current['close'] # Enter at close of the flip candle
            tp = entry * (1.0 + 0.005)
            sl = entry * (1.0 - 0.015)
            trades.append({'time': current['time'], 'direction': 'LONG', 'entry': entry, 'sl': sl, 'tp': tp})
            
        elif shortCondition:
            entry = current['close']
            tp = entry * (1.0 - 0.005)
            sl = entry * (1.0 + 0.015)
            trades.append({'time': current['time'], 'direction': 'SHORT', 'entry': entry, 'sl': sl, 'tp': tp})

    print(f"Generated {len(trades)} signals. Simulating outcomes...")
    
    # Simplified outcome simulation
    for trade in trades:
        future_data = df[df['time'] > trade['time']]
        for _, candle in future_data.iterrows():
            if trade['direction'] == 'LONG':
                if candle['low'] <= trade['sl']:
                    losses += 1
                    capital -= 10.0 # Strict $10 risk
                    break
                elif candle['high'] >= trade['tp']:
                    wins += 1
                    capital += 3.33 # If risking $10 for 1.5%, then 0.5% TP is 1/3 of the risk ($3.33)
                    break
            else:
                if candle['high'] >= trade['sl']:
                    losses += 1
                    capital -= 10.0
                    break
                elif candle['low'] <= trade['tp']:
                    wins += 1
                    capital += 3.33
                    break
                    
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pnl = capital - 1000.0
    
    report = f"# Rapid Fire Backtest Results ({symbol} | {interval})\n\n"
    report += f"- **Strategy:** PSAR Flip + SMA 50\n"
    report += f"- **Interval:** {interval}\n"
    report += f"- **Period:** Last {days} Days\n"
    report += f"- **Initial Capital:** $1,000.00\n"
    report += f"- **Final Capital:** ${capital:,.2f}\n"
    report += f"- **Net PnL:** ${pnl:,.2f}\n"
    report += f"- **Total Trades:** {total_trades}\n"
    report += f"- **Win Rate:** {win_rate:.2f}%\n"
    report += f"- **Wins:** {wins} | **Losses:** {losses}\n"
    report += f"- **Risk/Reward:** Inverted (Risk $10 to make $3.33)\n\n"
    
    from file_store import write_file
    write_file("backtest_results.md", report, mode="a")
        
    print(report)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CryptoTradingAssistant Backtest Engine")
    parser.add_argument("--strategy", type=str, help="Strategy to run: 'SMC' or 'Rapid Fire'")
    parser.add_argument("--symbol", type=str, help="Ticker symbol to test")
    parser.add_argument("--days", type=int, help="Number of days to look back")
    parser.add_argument("--interval", type=str, help="Timeframe interval (e.g. 5m, 15m)")
    parser.add_argument("--htf_interval", type=str, default="4h", help="Higher timeframe interval for bias (SMC only)")
    parser.add_argument("--grid", action="store_true", help="Run the default hardcoded Grid Search")
    args = parser.parse_args()

    from file_store import write_file

    if args.grid:
        write_file("backtest_results.md", "# MULTI-TIMEFRAME GRID SEARCH RESULTS (7D & 30D)\n\n", mode="w")
        print("Starting Grid Search...")
        smc_matrix = [("5m", "4h"), ("15m", "4h"), ("1h", "1d")]
        for days_lookback in [7, 30]:
            for interval, htf in smc_matrix:
                backtest_smc(symbol="BTC-USD", days=days_lookback, interval=interval, htf_interval=htf)
            rf_intervals = ["1m", "5m", "15m"]
            for interval in rf_intervals:
                if interval == "1m" and days_lookback == 30:
                    continue
                backtest_rapid_fire(symbol="BTC-USD", days=days_lookback, interval=interval)
    else:
        if not args.strategy or not args.symbol or not args.days or not args.interval:
            print("Missing arguments. Provide --strategy, --symbol, --days, --interval or use --grid")
            exit(1)
            
        print(f"Executing scheduled backtest: {args.strategy} on {args.symbol} for {args.days} days ({args.interval})")
        # Initialize the file if it doesn't exist, but append otherwise
        if args.strategy.upper() == "SMC":
            backtest_smc(symbol=args.symbol, days=args.days, interval=args.interval, htf_interval=args.htf_interval)
        elif args.strategy.upper() in ["RAPID FIRE", "RAPID_FIRE", "RAPIDFIRE"]:
            backtest_rapid_fire(symbol=args.symbol, days=args.days, interval=args.interval)
        else:
            print(f"Unknown strategy: {args.strategy}")
