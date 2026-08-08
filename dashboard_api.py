import os
import json
import sqlite3
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='dashboard/dist')
CORS(app)

DB_FILE = "market_data.db"
HISTORY_FILE = "ai_trade_history.json"
MASTER_BRAIN_FILE = "master_brain.md"
BACKTEST_FILE = "backtest_results.md"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# API Endpoints
@app.route('/api/master_brain', methods=['GET'])
def get_master_brain():
    try:
        with open(MASTER_BRAIN_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/backtest_results', methods=['GET'])
def get_backtest_results():
    try:
        if os.path.exists(BACKTEST_FILE):
            with open(BACKTEST_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"content": content})
        return jsonify({"content": "No backtest results available."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trade_history', methods=['GET'])
def get_trade_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/market_data/<symbol>/<interval>', methods=['GET'])
def get_market_data(symbol, interval):
    try:
        conn = get_db_connection()
        table_name = f"ohlcv_{interval}"
        
        # Get the latest 100 candles
        query = f"SELECT * FROM {table_name} WHERE symbol=? ORDER BY time DESC LIMIT 100"
        rows = conn.execute(query, (symbol,)).fetchall()
        conn.close()
        
        data = [dict(row) for row in rows]
        data.reverse() # Return chronological
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/system_status', methods=['GET'])
def get_system_status():
    return jsonify({
        "status": "ONLINE",
        "api_connected": True,
        "database_synced": os.path.exists(DB_FILE),
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
