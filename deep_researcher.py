import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from google import genai
from google.genai import types

from bot_runner import fetch_candles, TARGET_SYMBOLS

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

# --- Master Brain Management ---
def get_master_brain():
    if os.path.exists(MASTER_BRAIN_FILE):
        with open(MASTER_BRAIN_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "# Master Trading Brain\nThis is the core context file. It is currently empty. Start recording your knowledge here."

def append_master_brain(agent_name, content):
    with open(MASTER_BRAIN_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n\n### {agent_name} Update ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n{content}")

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
        "3. If nothing is new, reply EXACTLY with 'NO_UPDATE'."
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
        "3. Write a 1-paragraph summary of structural observations and rules to append to the master brain."
    )
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(temperature=0.3))
        append_master_brain("Technical Quant", response.text.strip())
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
        "3. Write a 1-paragraph rule to append to the master brain."
    )
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=types.GenerateContentConfig(temperature=0.3))
        append_master_brain("Risk Manager", response.text.strip())
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
        "3. Keep the entire document under 500 words.\n"
        f"--- RAW BRAIN ---\n{current_brain}\n"
    )
    
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        compacted = "# Master Trading Brain (Distilled)\n\n" + response.text.strip()
        with open(MASTER_BRAIN_FILE, "w", encoding="utf-8") as f:
            f.write(compacted)
        print("✅ Master Brain successfully compacted and noise removed.")
    except Exception as e:
        print(f"❌ Failed to compact brain: {e}")

def compile_morning_strategy():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌅 Morning has arrived. Portfolio Manager compiling strategy...")
    if not client: return
        
    current_brain = get_master_brain()
    
    pm_prompt = (
        "You are the Head Portfolio Manager. Read the following master knowledge base accumulated over the night.\n"
        f"--- MASTER BRAIN ---\n{current_brain[-5000:]}\n\n"
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
        config_data = json.loads(cleaned_json)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
        print("✅ Morning Strategy Config generated successfully.")
    except Exception as e:
        print(f"❌ Failed to compile strategy: {e}")

# --- Infinite Loop ---
def deep_research_loop():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🏢 Hedge Fund Night Shift Started.")
    
    loop_count = 0
    while True:
        now = datetime.now()
        
        # 07:55 AM -> Compact the brain
        if now.hour == 7 and now.minute >= 55:
            compact_master_brain()
            
        # 08:00 AM -> Portfolio Manager takes over, then exit script
        if now.hour == 8 and now.minute < 10:
            compile_morning_strategy()
            print("Night shift complete. Handing off to trading bot.")
            break
            
        # Active Shift: 20:00 (8 PM) to 07:54 AM
        if now.hour >= 20 or now.hour < 8:
            # 1. Macro Analyst runs every 5 minutes (every loop)
            run_macro_agent()
            
            # 2. Quant & Risk Agents run every 60 minutes (every 12th loop)
            if loop_count % 12 == 0:
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
