import json
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

def evaluate_predictions(history_file="ai_trade_history.json"):
    if not os.path.exists(history_file):
        print("No AI Trade History found. Run the Catalyst Scanner first.")
        return

    with open(history_file, "r") as f:
        history = json.load(f)

    if not history:
        print("Archive is empty.")
        return

    print(f"📊 Evaluating {len(history)} AI Swing Trade Predictions...\n")
    
    total_trades = 0
    wins = 0
    losses = 0
    pending = 0

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
            
        print(f"Analyzing {ticker} ({direction}) from {date_issued} | Entry: {entry} | TP: {tp} | SL: {sl}")
        
        # 1. Fetch Price action since the prediction date
        try:
            data = yf.download(ticker, start=date_issued, progress=False)
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
        
        for index, row in data.iterrows():
            high = row['high']
            low = row['low']
            
            # Since this is daily data, we check both SL and TP
            if direction == "LONG":
                if low <= sl:
                    trade_status = "LOSS (SL Hit)"
                    break
                elif high >= tp:
                    trade_status = "WIN (TP Hit)"
                    break
            else: # SHORT
                if high >= sl:
                    trade_status = "LOSS (SL Hit)"
                    break
                elif low <= tp:
                    trade_status = "WIN (TP Hit)"
                    break
                    
        print(f"  -> Result: {trade_status}")
        
        if "WIN" in trade_status:
            wins += 1
            total_trades += 1
        elif "LOSS" in trade_status:
            losses += 1
            total_trades += 1
        else:
            pending += 1

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
    return report

if __name__ == "__main__":
    evaluate_predictions()
