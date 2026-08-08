import { useEffect, useState } from 'react';
import { Activity, Brain, TrendingUp, BarChart2 } from 'lucide-react';

interface Trade {
  ticker: string;
  direction: string;
  entry_price: number;
  take_profit: number;
  stop_loss: number;
  date_issued: string;
  setup_context?: string;
  catalyst_title?: string;
}

interface SystemStatus {
  status: string;
  api_connected: boolean;
  database_synced: boolean;
  bot_active: boolean;
}

function App() {
  const [masterBrain, setMasterBrain] = useState<string>('Loading Master Brain...');
  const [history, setHistory] = useState<Trade[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [backtests, setBacktests] = useState<string>('Loading Backtest Results...');

  // In production, we assume the API is hosted on the same origin. 
  // For local Vite dev, we'd need to proxy, but for simplicity here we just use relative path 
  // (which will work once compiled and served by Flask) or absolute for dev.
  const API_BASE = window.location.port === '5173' ? 'http://127.0.0.1:8080' : '';

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [brainRes, histRes, statRes, backRes] = await Promise.all([
          fetch(`${API_BASE}/api/master_brain`).catch(() => null),
          fetch(`${API_BASE}/api/trade_history`).catch(() => null),
          fetch(`${API_BASE}/api/system_status`).catch(() => null),
          fetch(`${API_BASE}/api/backtest_results`).catch(() => null),
        ]);

        if (brainRes?.ok) {
          const data = await brainRes.json();
          setMasterBrain(data.content || 'Master Brain is empty.');
        }
        
        if (histRes?.ok) {
          const data = await histRes.json();
          setHistory(data.reverse()); // Newest first
        }

        if (statRes?.ok) {
          const data = await statRes.json();
          setStatus(data);
        }
        
        if (backRes?.ok) {
          const data = await backRes.json();
          setBacktests(data.content || 'No backtest results available.');
        }
      } catch (err) {
        console.error('Failed to fetch data', err);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [API_BASE]);

  return (
    <div className="dashboard-grid">
      <div className="header">
        <h1>Autonomous Family Office</h1>
        <div className="status-badge">
          <div className="status-indicator"></div>
          {status ? 'SYSTEM ONLINE' : 'CONNECTING...'}
        </div>
      </div>

      <div className="glass-panel" style={{ gridColumn: 'span 2' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 0 }}>
          <Brain size={24} color="#a0a0a0" />
          Master Brain Context
        </h2>
        <div className="markdown-content" style={{ whiteSpace: 'pre-wrap' }}>
          {masterBrain}
        </div>
      </div>

      <div className="glass-panel">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 0 }}>
          <Activity size={24} color="#a0a0a0" />
          Active Intelligence
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
            <span style={{ color: '#a0a0a0' }}>Database Sync</span>
            <span style={{ color: status?.database_synced ? '#10b981' : '#ef4444', fontWeight: 500 }}>
              {status?.database_synced ? 'SYNCED' : 'PENDING'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
            <span style={{ color: '#a0a0a0' }}>API Connection</span>
            <span style={{ color: status?.api_connected ? '#10b981' : '#ef4444', fontWeight: 500 }}>
              {status?.api_connected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
            <span style={{ color: '#a0a0a0' }}>Bot Execution Engine</span>
            <span style={{ color: status?.bot_active ? '#10b981' : '#ef4444', fontWeight: 500 }}>
              {status?.bot_active ? 'ACTIVE' : 'IDLE'}
            </span>
          </div>
        </div>
      </div>
      
      <div className="glass-panel" style={{ gridColumn: 'span 3' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 0 }}>
          <BarChart2 size={24} color="#a0a0a0" />
          Strategy Performance (Backtest Engine)
        </h2>
        <div className="markdown-content" style={{ whiteSpace: 'pre-wrap', maxHeight: '400px', overflowY: 'auto', paddingRight: '10px' }}>
          {backtests}
        </div>
      </div>

      <div className="glass-panel" style={{ gridColumn: 'span 3' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 0 }}>
          <TrendingUp size={24} color="#a0a0a0" />
          AI Swing Trade Predictions
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px', marginTop: '20px' }}>
          {history.length > 0 ? (
            history.slice(0, 6).map((trade, idx) => (
              <div key={idx} className="trade-card">
                <div className="trade-header">
                  <div className="trade-ticker">{trade.ticker}</div>
                  <div className={`trade-direction ${trade.direction.toLowerCase()}`}>
                    {trade.direction}
                  </div>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#a0a0a0', marginBottom: '16px', lineHeight: '1.4' }}>
                  {trade.catalyst_title || trade.setup_context}
                </div>
                <div className="trade-details">
                  <div>
                    Entry
                    <strong>${trade.entry_price?.toLocaleString() || 'N/A'}</strong>
                  </div>
                  <div>
                    Target
                    <strong style={{ color: trade.direction === 'LONG' ? '#10b981' : '#ef4444' }}>
                      ${trade.take_profit?.toLocaleString() || 'N/A'}
                    </strong>
                  </div>
                  <div>
                    Stop Loss
                    <strong style={{ color: trade.direction === 'LONG' ? '#ef4444' : '#10b981' }}>
                      ${trade.stop_loss?.toLocaleString() || 'N/A'}
                    </strong>
                  </div>
                </div>
                <div style={{ marginTop: '16px', fontSize: '0.75rem', color: '#666', textAlign: 'right' }}>
                  Issued: {trade.date_issued}
                </div>
              </div>
            ))
          ) : (
            <div style={{ color: '#a0a0a0', fontStyle: 'italic' }}>No predictions recorded yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
