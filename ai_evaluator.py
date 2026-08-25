import json
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

def evaluate_predictions(history_file="ai_trade_history.json"):
    from file_store import read_file
    content = read_file(history_file)
    if not content:
        print("No AI Trade History found. Run the Catalyst Scanner first.")
        return

    history = json.loads(content)

    if not history:
        print("Archive is empty.")
        return

    print(f"📊 Evaluating {len(history)} AI Swing Trade Predictions...\n")
    
    total_trades = 0
    wins = 0
    losses = 0
    pending = 0
    db_trades = []
    
    from db import get_engine
    engine = get_engine()
    try:
        existing_df = pd.read_sql("SELECT symbol, entry_time FROM ai_backtests", engine)
        processed_signatures = set(existing_df['symbol'] + "_" + existing_df['entry_time'])
    except Exception:
        processed_signatures = set()

    for trade in history:
        ticker = trade.get('ticker')
        direction = trade.get('direction', 'LONG').upper()
        entry = trade.get('entry_price')
        tp = trade.get('take_profit')
        sl = trade.get('stop_loss')
        date_issued = trade.get('date_issued')
        title = trade.get('catalyst_title', 'Unknown Catalyst')
        
        if not all([ticker, entry, tp, sl, date_issued]):
            print(f"⚠️ Skipping '{title}' due to missing structural data.")
            continue
            
        signature = f"{ticker}_{date_issued}"
        if signature in processed_signatures:
            # We don't increment pending or totals, it's just completely skipped.
            continue
            
        print(f"Analyzing {ticker} ({direction}) from {date_issued} | Entry: {entry} | TP: {tp} | SL: {sl}")
        
        # Clean ticker for yfinance compatibility
        yf_ticker = ticker.upper().strip()
        if yf_ticker in ["XAU/USD", "XAUUSD"]:
            yf_ticker = "GC=F"
        elif yf_ticker == "EUR/USD":
            yf_ticker = "EURUSD=X"
        elif yf_ticker.endswith("-USDT"):
            yf_ticker = yf_ticker.replace("-USDT", "-USD")
            
        try:
            data = yf.download(yf_ticker, start=date_issued, progress=False)
        except Exception:
            print(f"  -> ❌ Failed to download historical data for {ticker}")
            continue
            
        if data.empty:
            print(f"  -> 🕒 Data not available yet or invalid ticker.")
            pending += 1
            continue

        # Convert column names to lowercase to make parsing easier (multi-index handling for yfinance 0.2+)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [c[0].lower() for c in data.columns]
        else:
            data.columns = [c.lower() for c in data.columns]

        # 2. Simulate the Trade (Aggressive grading: assumes entry was filled immediately)
        trade_status = "PENDING"
        max_price = entry
        min_price = entry
        exit_time = None
        exit_price = None
        pnl_percent = 0.0
        
        for index, row in data.iterrows():
            high = row['high']
            low = row['low']
            if high > max_price: max_price = high
            if low < min_price: min_price = low
            
            # Since this is daily data, we check both SL and TP
            if direction == "LONG":
                if low <= sl:
                    trade_status = "LOSS (SL Hit)"
                    exit_time = index
                    exit_price = sl
                    pnl_percent = ((sl - entry)/entry)*100
                    break
                elif high >= tp:
                    trade_status = "WIN (TP Hit)"
                    exit_time = index
                    exit_price = tp
                    pnl_percent = ((tp - entry)/entry)*100
                    break
            else: # SHORT
                if high >= sl:
                    trade_status = "LOSS (SL Hit)"
                    exit_time = index
                    exit_price = sl
                    pnl_percent = ((entry - sl)/entry)*100
                    break
                elif low <= tp:
                    trade_status = "WIN (TP Hit)"
                    exit_time = index
                    exit_price = tp
                    pnl_percent = ((entry - tp)/entry)*100
                    break
                    
        # Calculate MAE / MFE
        mae_percent = 0.0
        mfe_percent = 0.0
        if direction == 'LONG':
            mae_percent = ((min_price - entry)/entry)*100
            mfe_percent = ((max_price - entry)/entry)*100
        else:
            mae_percent = ((entry - max_price)/entry)*100
            mfe_percent = ((entry - min_price)/entry)*100
            
        print(f"  -> Result: {trade_status}")
        
        if "WIN" in trade_status:
            wins += 1
            total_trades += 1
            status = 'WIN'
        elif "LOSS" in trade_status:
            losses += 1
            total_trades += 1
            status = 'LOSS'
        else:
            pending += 1
            status = 'OPEN'
            
        if status != 'OPEN':
            db_trades.append({
                'strategy': 'AI_SWING',
                'symbol': ticker,
                'direction': direction,
                'entry_time': date_issued,
                'entry_price': entry,
                'exit_time': exit_time,
                'exit_price': exit_price,
                'pnl_percent': pnl_percent,
                'mae_percent': mae_percent,
                'mfe_percent': mfe_percent,
                'status': status
            })

    report = "📈 **AI CATALYST PREDICTION PERFORMANCE** 📈\n"
    report += f"Total Completed Trades : {total_trades}\n"
    report += f"Wins                   : {wins}\n"
    report += f"Losses                 : {losses}\n"
    report += f"Pending/Active         : {pending}\n"
    
    if total_trades > 0:
        win_rate = (wins / total_trades) * 100
        report += f"Win Rate               : {win_rate:.2f}%\n"
        
        if win_rate > 50:
            report += "\n✅ The AI is currently generating profitable alpha.\n"
        else:
            report += "\n❌ The AI predictions are underperforming. Consider adjusting prompts or risk limits.\n"
    else:
        report += "\nNo trades have completed yet.\n"
        
    print(report)
    
    if db_trades:
        pd.DataFrame(db_trades).to_sql('ai_backtests', engine, if_exists='append', index=False)
        
    return report

if __name__ == "__main__":
    evaluate_predictions()
