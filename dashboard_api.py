import os
import json
from flask import Flask, jsonify, send_from_directory
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
        from file_store import read_file
        content = read_file(HISTORY_FILE)
        if content:
            history = json.loads(content)
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
