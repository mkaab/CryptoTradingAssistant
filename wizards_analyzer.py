import pandas as pd
import numpy as np
from sqlalchemy import text
from db import get_engine

def get_dxy_direction(engine, entry_time):
    # Get the DXY daily candle corresponding to the entry time
    try:
        # Convert timestamp to date for matching
        date_str = pd.to_datetime(entry_time).strftime('%Y-%m-%d')
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT open, close FROM ohlcv_1d WHERE symbol = 'DX-Y.NYB' AND time LIKE '{date_str}%' LIMIT 1")).fetchone()
            if result:
                return "Bullish" if result[1] >= result[0] else "Bearish"
    except:
        pass
    return "Unknown"

def calculate_max_drawdown(pnl_series):
    cum_returns = pnl_series.cumsum()
    running_max = cum_returns.cummax()
    drawdown = cum_returns - running_max
    return abs(drawdown.min())

def analyze_table(table_name, engine):
    try:
        df = pd.read_sql_table(table_name, engine)
    except Exception as e:
        return f"Could not load {table_name}: {e}\n"
        
    if df.empty:
        return f"No trades found in {table_name}.\n"
        
    # Standard Metrics
    total_trades = len(df)
    wins = len(df[df['pnl_percent'] > 0])
    losses = len(df[df['pnl_percent'] < 0])
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    total_return = df['pnl_percent'].sum()
    
    # MAE / MFE
    avg_mae = df['mae_percent'].mean()
    avg_mfe = df['mfe_percent'].mean()
    
    # Unknown Market Wizards Metrics
    sum_gains = df[df['pnl_percent'] > 0]['pnl_percent'].sum()
    sum_losses = abs(df[df['pnl_percent'] < 0]['pnl_percent'].sum())
    
    gpr = sum_gains / sum_losses if sum_losses > 0 else float('inf')
    
    # Sort chronologically for equity curve / Max Drawdown
    df = df.sort_values(by='entry_time')
    max_dd = calculate_max_drawdown(df['pnl_percent'])
    return_to_dd = total_return / max_dd if max_dd > 0 else float('inf')
    
    # Macro Alignment (DXY)
    df['dxy_state'] = df['entry_time'].apply(lambda x: get_dxy_direction(engine, x))
    
    report = f"## 📊 Analytics for `{table_name}`\n"
    report += f"- **Total Trades:** {total_trades}\n"
    report += f"- **Win Rate:** {win_rate:.2f}%\n"
    report += f"- **Total Return:** {total_return:.2f}%\n"
    report += f"- **Avg MAE (Adverse):** {avg_mae:.2f}% (Average drawdown during a trade)\n"
    report += f"- **Avg MFE (Favorable):** {avg_mfe:.2f}% (Average peak profit during a trade)\n"
    
    report += f"\n### 🧙‍♂️ Unknown Market Wizards Metrics\n"
    report += f"- **Gain to Pain Ratio (GPR):** {gpr:.2f} *(Ideal > 1.0)*\n"
    report += f"- **Max Drawdown:** {max_dd:.2f}%\n"
    report += f"- **Return / Max Drawdown:** {return_to_dd:.2f} *(Ideal > 2.0)*\n"
    
    report += f"\n### 🌍 Macro Alignment (DXY Impact)\n"
    
    # Analyze by DXY state and Direction
    for dxy in ["Bullish", "Bearish"]:
        for direction in ["LONG", "SHORT"]:
            subset = df[(df['dxy_state'] == dxy) & (df['direction'] == direction)]
            if not subset.empty:
                wr = (len(subset[subset['pnl_percent'] > 0]) / len(subset)) * 100
                report += f"- **{direction}** Trades when DXY is **{dxy}**: {wr:.1f}% Win Rate ({len(subset)} trades)\n"
                
    report += "\n---\n"
    return report

def generate_insights():
    print("Generating Market Wizards Insights...")
    engine = get_engine()
    
    report = "# 🧙‍♂️ Market Wizards Analytics Report\n\n"
    report += analyze_table("smc_backtests", engine)
    report += analyze_table("ai_backtests", engine)
    
    from file_store import write_file
    write_file("market_wizards_insights.md", report, mode="w")
    
    # Also append it to the Master Brain so it shows on the Dashboard
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    brain_append = f"\n\n## Market Wizards Analytics ({today})\n{report}\n"
    write_file("master_brain.md", brain_append, mode="a")
    
    print("\n" + report)
    print("Report saved to market_wizards_insights.md and appended to master_brain.md")

if __name__ == "__main__":
    generate_insights()
