import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from google import genai
from google.genai import types

from bot_runner import fetch_candles, TARGET_SYMBOLS
from file_store import read_file, write_file

load_dotenv()

try:
    client = genai.Client()
except Exception as e:
    print(f"Failed to initialize Gemini Client: {e}")
    client = None

MASTER_BRAIN_FILE = "master_brain.md"
CONFIG_FILE = "ai_strategy_config.json"

# --- Data Fetching ---
def get_todays_price_action():
    """Fetches a high-level summary of today's price action for the Quant to read."""
    summary = ""
    for symbol in TARGET_SYMBOLS:
        df = fetch_candles(symbol, '4H')
        if df.empty:
            continue
            
        # Get only the last 24 hours of data (6 candles on 4H)
        today_df = df.tail(6)
        if today_df.empty:
            continue
            
        open_price = today_df.iloc[0]['open']
        close_price = today_df.iloc[-1]['close']
        high_price = today_df['high'].max()
        low_price = today_df['low'].min()
        
        move_pct = ((close_price - open_price) / open_price) * 100
        volatility_pct = ((high_price - low_price) / low_price) * 100
        
        summary += f"\nSymbol: {symbol}\n"
        summary += f"- Open: {open_price:.4f} | Close: {close_price:.4f}\n"
        summary += f"- Net Move: {move_pct:.2f}%\n"
        summary += f"- Volatility (High-Low spread): {volatility_pct:.2f}%\n"
    
    return summary

def get_master_brain():
    content = read_file(MASTER_BRAIN_FILE)
    if content:
        return content
    return "# Master Trading Brain\nThis is the core context file. It is currently empty. Start recording your knowledge here."

def append_master_brain(agent_name, content):
    entry = f"\n\n### {agent_name} Update ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n{content}"
    write_file(MASTER_BRAIN_FILE, entry, mode="a")

# --- Agent Personas ---
def run_macro_agent():
    """Uses Google Search to pull live economic news."""
    if not client: return
    
    current_brain = get_master_brain()
    prompt = (
        "You are the Lead Quantitative Researcher for a Hedge Fund. "
        "Your primary task is to search Google Scholar and Arxiv for novel, mathematically proven trading edges, "
        "unconventional quantitative strategies, and market inefficiencies (e.g., statistical arbitrage, volatility clustering, order flow imbalance) "
        "that retail traders haven't spotted yet. You should also check for major Macroeconomic news (CPI, FOMC, Yield Curve).\n\n"
        f"--- FIRM'S MASTER BRAIN ---\n{current_brain[-4000:]}\n\n"
        "Instructions:\n"
        "1. Search the web for recent academic research papers on financial markets, crypto, or forex.\n"
        "2. If you find a novel strategy or a major macro event, write a 1-paragraph brief distilling the mathematical edge or rule we should adopt.\n"
        "3. CRITICAL DEDUPLICATION RULE: Review the Firm's Master Brain above. Do NOT repeat observations that are already documented. Only append NEW insights, shifting trends, or contradictions.\n"
        "4. If nothing is new, reply EXACTLY with 'NO_UPDATE'."
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(tools=[{"google_search": {}}], temperature=0.4)
        )
        output = response.text.strip()
        if output and "NO_UPDATE" not in output:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📰 Macro Analyst reported new findings.")
            append_master_brain("Macro Analyst", output)
    except Exception as e:
        print(f"Macro Agent Error: {e}")

def run_cio_agent():
    """
    The Chief Investment Officer.
    Runs at 07:50 AM to correlate Macro, Micro, and Math.
    Overwrites the Master Brain with a synthesized Correlation Matrix.
    """
    if not client: return
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 👔 CIO Agent synthesizing correlation matrix...")
    current_brain = get_master_brain()
    
    from data_manager import calculate_correlation_matrix
    math_matrix = calculate_correlation_matrix(30)
    
    # Load Macro Context (Catalysts, Congress, Multi-month swings)
    macro_context = "No historical long-term catalysts found."
    try:
        content = read_file("ai_trade_history.json")
        if content:
            history = json.loads(content)
            macro_context = json.dumps(history[-10:], indent=2) # Last 10 major fundamental events
    except Exception:
        pass
                
    prompt = (
        "You are the Chief Investment Officer (CIO) of an autonomous AI hedge fund.\n"
        "Your analysts have been dumping unorganized intelligence into the Master Brain all night. "
        "Your job is to read all of it, correlate it, and output a strict, synthesized 'Cross-Market Correlation Matrix'.\n\n"
        "CRITICAL RULE: You must base all your correlations on the hard mathematical precedence provided below. Do NOT hallucinate correlations. "
        "If Gold and BTC have a negative correlation mathematically, you must factor that in when reading the Macro Agent's gold report.\n\n"
        "--- 1. MACRO/FUNDAMENTAL CONTEXT (3-Month Horizon) ---\n"
        "These are major catalysts and congressional trades dictating the long-term trend:\n"
        f"{macro_context}\n\n"
        "--- 2. MATHEMATICAL CORRELATIONS (30-Day Horizon) ---\n"
        f"{math_matrix}\n\n"
        f"--- 3. RAW OVERNIGHT RESEARCH (Daily Horizon) ---\n{current_brain}\n\n"
        "Instructions:\n"
        "1. Synthesize the raw Master Brain.\n"
        "2. Cross-reference the agent findings with the exact mathematical correlation matrix provided.\n"
        "3. Output a highly organized report detailing where Macro, Micro, and Math align (High Probability) and where they contradict (Do Not Trade).\n"
        "This output will become the NEW Master Brain."
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        output = response.text.strip()
        
        # Overwrite the chaotic brain with the CIO's synthesized matrix
        write_file(MASTER_BRAIN_FILE, "# 👔 CIO Cross-Market Correlation Matrix\n\n" + output)
            
        print("✅ CIO successfully synthesized the Master Brain.")
    except Exception as e:
        print(f"CIO Agent Error: {e}")

def run_quant_agent():
    """Reads 4H price action and math to dictate structural trends."""
    if not client: return
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧮 Quant Agent pulling market data...")
    market_data = get_todays_price_action()
    current_brain = get_master_brain()
    
    prompt = (
        "You are the Lead Quantitative Analyst for a Hedge Fund. You focus purely on math, price action, and structure. "
        f"--- TODAY'S DATA ---\n{market_data}\n\n"
        f"--- FIRM'S MASTER BRAIN ---\n{current_brain[-4000:]}\n\n"
        "Instructions:\n"
        "1. Review the OHLCV net movements and volatility for the day.\n"
        "2. Is the market trending strongly, or is it choppy? What asset is outperforming?\n"
        "3. CRITICAL DEDUPLICATION RULE: Review the Firm's Master Brain above. Do NOT repeat structural observations that are already documented unless the structure has explicitly broken. Only append NEW insights.\n"
        "4. Write a 1-paragraph summary of structural observations and rules to append to the master brain. If nothing is new, reply EXACTLY with 'NO_UPDATE'."
    )
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(temperature=0.3))
        output = response.text.strip()
        if output and "NO_UPDATE" not in output:
            append_master_brain("Technical Quant", output)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧮 Quant Agent updated the Master Brain.")
    except Exception as e:
        print(f"Quant Agent Error: {e}")

def run_risk_agent():
    """Reads the master brain and dictates risk thresholds."""
    if not client: return
    
    current_brain = get_master_brain()
    prompt = (
        "You are the Chief Risk Officer. Your only job is capital preservation.\n"
        f"--- FIRM'S MASTER BRAIN ---\n{current_brain[-4000:]}\n\n"
        "Instructions:\n"
        "1. Read the latest notes from the Macro Analyst and the Quant.\n"
        "2. Define the exact risk parameters. Should we widen stop losses due to extreme chop? Should we cut size?\n"
        "3. CRITICAL DEDUPLICATION RULE: Review the Firm's Master Brain above. Do NOT repeat risk parameters that are already active unless they need to be changed.\n"
        "4. Write a 1-paragraph rule to append to the master brain. If no changes to risk are needed, reply EXACTLY with 'NO_UPDATE'."
    )
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(temperature=0.3))
        output = response.text.strip()
        if output and "NO_UPDATE" not in output:
            append_master_brain("Risk Manager", output)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ Risk Manager updated the Master Brain.")
    except Exception as e:
        print(f"Risk Agent Error: {e}")

# --- Compaction & Morning Orchestration ---
def compact_master_brain():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧹 Distilling Master Brain to remove noise...")
    if not client: return
        
    current_brain = get_master_brain()
    if len(current_brain) < 2000: return
        
    prompt = (
        "You are a strict Quantitative Hedge Fund Manager. Below is the raw, bloated research log from the Night Shift.\n"
        "Your job is to rewrite this into a hyper-condensed 'Core Principles' document.\n"
        "RULES:\n"
        "1. Discard all temporary/expired news (e.g., 'CPI data released today').\n"
        "2. Keep ONLY permanent, structural truths (e.g., 'Gold tends to whipsaw 0.3% around 8:30 AM data releases').\n"
        "3. PERSISTENT TIMESTAMPING: Preserve the chronology! You must attach the original date/time to every structural truth you compress, so we know WHEN it happened.\n"
        "4. Keep the entire document under 500 words.\n"
        f"--- RAW BRAIN ---\n{current_brain}\n"
    )
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        compacted = "# Master Trading Brain (Distilled)\n\n" + response.text.strip()
        write_file(MASTER_BRAIN_FILE, compacted)
        print("✅ Master Brain successfully compacted and noise removed.")
    except Exception as e:
        print(f"❌ Failed to compact brain: {e}")

def compile_morning_strategy():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌅 Morning has arrived. Portfolio Manager compiling strategy...")
    if not client: return
        
    current_brain = get_master_brain()
    
    # Load Micro Context (Backtest Performance)
    micro_context = read_file("backtest_results.md", default_content="No backtest results available.")
            
    pm_prompt = (
        "You are the Head Portfolio Manager. Read the following master knowledge base accumulated over the night, "
        "as well as the latest Backtest Results to see which strategy is mathematically winning right now.\n\n"
        f"--- MASTER BRAIN (MACRO/FUNDAMENTALS) ---\n{current_brain[-5000:]}\n\n"
        f"--- BACKTEST RESULTS (MICRO/STRATEGY) ---\n{micro_context}\n\n"
        "Based on all this research, output a STRICT JSON configuration file that will dictate how the trading bot behaves today.\n"
        "Your output must be ONLY valid JSON, no markdown formatting.\n"
        "The JSON MUST follow this exact structure:\n"
        "{\n"
        '  "whipsaw_buffer_pct": 0.2, // standard is 0.2, increase to 0.4 if volatility is high\n'
        '  "allowed_direction": "BOTH", // can be "LONG_ONLY", "SHORT_ONLY", or "BOTH" based on trend\n'
        '  "base_rr_multiplier": 2 // usually 2, increase to 3 if market conditions are prime\n'
        "}\n"
    )
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=pm_prompt)
        cleaned_json = response.text.replace('```json', '').replace('```', '').strip()
        cleaned = json.loads(cleaned_json)
        write_file(CONFIG_FILE, json.dumps(cleaned, indent=4))
        print("✅ Portfolio Manager successfully set strategy config for today.")
        
        # Send Discord Alert with the strategy
        from bot_runner import send_discord_alert
        msg = (
            f"🌅 **Morning Shift Complete** 🌅\n"
            f"The AI Portfolio Manager has analyzed the overnight Master Brain and set today's strategy:\n"
            f"```json\n{json.dumps(cleaned, indent=2)}\n```\n"
            f"The bot is now fully armed for the London Killzone."
        )
        send_discord_alert(msg)
        
    except Exception as e:
        print(f"❌ Failed to compile strategy: {e}")

# --- Infinite Loop ---
def deep_research_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🏢 Hedge Fund Night Shift Started.")
    
    import subprocess
    print("Running initial overnight Backtests...")
    
    # 1. Sync the Local Database
    from data_manager import update_all_data
    update_all_data()
    
    # 2. Run the Multi-Timeframe Grid Search
    subprocess.run(["python", "backtest.py"])
    
    # 3. AI Evaluator (Self-Feedback Loop)
    print("Grading past AI predictions...")
    from ai_evaluator import evaluate_predictions
    report = evaluate_predictions()
    if report:
        append_master_brain("AI Performance Evaluator", report)
        
    loop_count = 0
    while True:
        now = datetime.now()
        
        # 07:50 AM -> Chief Investment Officer synthesizes the Brain
        if now.hour == 7 and now.minute == 50:
            run_cio_agent()
            
        # 07:55 AM -> Compact the brain (backup)
        if now.hour == 7 and now.minute >= 55:
            compact_master_brain()
            
        # 08:00 AM -> Portfolio Manager takes over, then exit script
        if now.hour == 8 and now.minute < 10:
            import subprocess
            import json
            from file_store import read_file, write_file
            
            print("Checking Backtest Queue...")
            queue_content = read_file("backtest_queue.json")
            if queue_content:
                queue = json.loads(queue_content)
                for test in queue:
                    print(f"Executing Scheduled Backtest: {test.get('hypothesis', 'Unknown')}")
                    # Build command
                    cmd = ["python", "backtest.py"]
                    if "strategy" in test: cmd.extend(["--strategy", str(test['strategy'])])
                    if "symbol" in test: cmd.extend(["--symbol", str(test['symbol'])])
                    if "days" in test: cmd.extend(["--days", str(test['days'])])
                    if "interval" in test: cmd.extend(["--interval", str(test['interval'])])
                    if "htf_interval" in test: cmd.extend(["--htf_interval", str(test['htf_interval'])])
                    
                    subprocess.run(cmd)
                
                # Clear queue
                write_file("backtest_queue.json", "[]", mode="w")
                
            print("Running Nightly AI Evaluator...")
            subprocess.run(["python", "ai_evaluator.py"])
            print("Generating Market Wizards Analytics...")
            subprocess.run(["python", "wizards_analyzer.py"])
            
            compile_morning_strategy()
            print("Night shift complete. Handing off to trading bot.")
            break
            
        # Active Shift: 20:00 (8 PM) to 07:54 AM
        if now.hour >= 20 or now.hour < 8:
            
            # All 3 Agents run every 3 hours (every 36th loop) to respect the strict 20-request/day Free Tier limit
            if loop_count % 36 == 0:
                run_macro_agent()
                run_quant_agent()
                run_risk_agent()
                
            loop_count += 1
            
            # Sleep 5 minutes
            time.sleep(300)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] It is currently daytime. Sleeping until 8 PM...")
            time.sleep(3600)

if __name__ == "__main__":
    deep_research_loop()
