import os
import json
import uuid
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import text
from db import get_engine

load_dotenv()

app = Flask(__name__, static_folder='dashboard/dist')
CORS(app)

HISTORY_FILE = "ai_trade_history.json"
MASTER_BRAIN_FILE = "master_brain.md"
BACKTEST_FILE = "backtest_results.md"

# API Endpoints
@app.route('/api/master_brain', methods=['GET'])
def get_master_brain():
    try:
        from file_store import read_file
        content = read_file(MASTER_BRAIN_FILE)
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/backtest_results', methods=['GET'])
def get_backtest_results():
    try:
        from file_store import read_file
        content = read_file(BACKTEST_FILE, "No backtest results available.")
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trade_history', methods=['GET'])
def get_trade_history():
    try:
        import pandas as pd
        engine = get_engine()
        df = pd.read_sql("SELECT * FROM active_ai_trades", engine)
        return jsonify(df.to_dict('records'))
    except Exception as e:
        print(f"Error fetching trade history: {e}")
        return jsonify([])

@app.route('/api/trading_journal', methods=['GET'])
def get_trading_journal():
    try:
        import pandas as pd
        engine = get_engine()
        # Fetch completed trades with context
        df = pd.read_sql("SELECT symbol, direction, entry_time, pnl_percent, status, catalyst_title, setup_context FROM ai_backtests ORDER BY entry_time DESC", engine)
        return jsonify(df.to_dict('records'))
    except Exception as e:
        print(f"Error fetching trading journal: {e}")
        return jsonify([])

@app.route('/api/market_data/<symbol>/<interval>', methods=['GET'])
def get_market_data(symbol, interval):
    try:
        engine = get_engine()
        table_name = f"ohlcv_{interval}"
        
        # Get the latest 100 candles
        query = text(f"SELECT * FROM {table_name} WHERE symbol=:symbol ORDER BY time DESC LIMIT 100")
        with engine.connect() as conn:
            result = conn.execute(query, {"symbol": symbol})
            rows = result.fetchall()
            
        data = [dict(row._mapping) for row in rows]
        data.reverse() # Return chronological
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/system_status', methods=['GET'])
def get_system_status():
    return jsonify({
        "status": "ONLINE",
        "api_connected": True,
        "database_synced": True,
        "bot_active": True # In a real scenario, we could check the bot_runner process
    })

# --- AI Hypothesis Backtest Endpoints ---

@app.route('/api/backtest_suggestions', methods=['GET'])
def get_backtest_suggestions():
    try:
        from google import genai
        from google.genai import types
        client = genai.Client()
        
        from file_store import read_file
        brain = read_file(MASTER_BRAIN_FILE, default_content="No brain data.")
        
        prompt = (
            "You are a Senior Quantitative Analyst. Look at the current market context:\n"
            f"{brain[-2000:]}\n\n"
            "Propose exactly 3 unique hypotheses for historical strategy backtests.\n"
            "Strategies available: 'SMC', 'Rapid Fire'.\n"
            "Symbols available: BTC-USD, ETH-USD, SOL-USD, GC=F (Gold).\n"
            "Intervals available: 1m, 5m, 15m, 1h. (SMC also needs htf_interval: 4h or 1d).\n"
            "Output MUST be strict JSON in this exact format:\n"
            "[\n"
            "  {\n"
            '    "hypothesis": "Test SMC on SOL 5m due to volatility spike",\n'
            '    "reasoning_summary": "SOL is showing 12% excess volatility. SMC usually captures deep pullbacks well in this regime.",\n'
            '    "strategy": "SMC",\n'
            '    "symbol": "SOL-USD",\n'
            '    "days": 7,\n'
            '    "interval": "5m",\n'
            '    "htf_interval": "4h"\n'
            "  }\n"
            "]\n"
        )
        
        from llm_utils import generate_with_retry
        response = generate_with_retry(
            client=client,
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        suggestions = json.loads(response.text)
        return jsonify(suggestions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/schedule_backtest', methods=['POST'])
def schedule_backtest():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        from file_store import read_file, write_file
        queue_content = read_file("backtest_queue.json")
        queue = json.loads(queue_content) if queue_content else []
        
        data["id"] = str(uuid.uuid4())
        data["status"] = "PENDING"
        queue.append(data)
        
        write_file("backtest_queue.json", json.dumps(queue, indent=4))
        return jsonify({"success": True, "message": "Backtest scheduled for Night Shift."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/backtest_queue', methods=['GET'])
def get_backtest_queue():
    try:
        from file_store import read_file
        queue_content = read_file("backtest_queue.json")
        queue = json.loads(queue_content) if queue_content else []
        return jsonify(queue)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serve React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    # Railway passes the port dynamically
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
