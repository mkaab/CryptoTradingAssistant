import { useEffect, useState } from 'react';
import { Activity, Brain, TrendingUp, BarChart2, Lightbulb, PlayCircle, Loader2 } from 'lucide-react';

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

interface BacktestSuggestion {
  hypothesis: string;
  reasoning_summary: string;
  strategy: string;
  symbol: string;
  days: number;
  interval: string;
  htf_interval?: string;
}

interface BacktestQueueItem extends BacktestSuggestion {
  id: string;
  status: string;
}

function App() {
  const [masterBrain, setMasterBrain] = useState<string>('Loading Master Brain...');
  const [history, setHistory] = useState<Trade[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [backtests, setBacktests] = useState<string>('Loading Backtest Results...');
  const [suggestions, setSuggestions] = useState<BacktestSuggestion[]>([]);
  const [queue, setQueue] = useState<BacktestQueueItem[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [journal, setJournal] = useState<any[]>([]);

  // In production, we assume the API is hosted on the same origin. 
  // For local Vite dev, we'd need to proxy, but for simplicity here we just use relative path 
  // (which will work once compiled and served by Flask) or absolute for dev.
  const API_BASE = window.location.port === '5173' ? 'http://127.0.0.1:8080' : '';

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [brainRes, histRes, statRes, backRes, queueRes, journalRes] = await Promise.all([
          fetch(`${API_BASE}/api/master_brain`).catch(() => null),
          fetch(`${API_BASE}/api/trade_history`).catch(() => null),
          fetch(`${API_BASE}/api/system_status`).catch(() => null),
          fetch(`${API_BASE}/api/backtest_results`).catch(() => null),
          fetch(`${API_BASE}/api/backtest_queue`).catch(() => null),
          fetch(`${API_BASE}/api/trading_journal`).catch(() => null),
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

        if (queueRes?.ok) {
          const data = await queueRes.json();
          setQueue(data);
        }

        if (journalRes?.ok) {
          const data = await journalRes.json();
          setJournal(data);
        }
      } catch (err) {
        console.error('Failed to fetch data', err);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [API_BASE]);

  const generateSuggestions = async () => {
    setLoadingSuggestions(true);
    try {
      const res = await fetch(`${API_BASE}/api/backtest_suggestions`);
      if (res.ok) {
        const data = await res.json();
        setSuggestions(data);
      }
    } catch (e) {
      console.error(e);
    }
    setLoadingSuggestions(false);
  };

  const scheduleBacktest = async (suggestion: BacktestSuggestion) => {
    try {
      const res = await fetch(`${API_BASE}/api/schedule_backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(suggestion)
      });
      if (res.ok) {
        // Refresh queue
        const qRes = await fetch(`${API_BASE}/api/backtest_queue`);
        if (qRes.ok) {
          const qData = await qRes.json();
          setQueue(qData);
        }
        // Remove from suggestions
        setSuggestions(s => s.filter(x => x.hypothesis !== suggestion.hypothesis));
      }
    } catch (e) {
      console.error(e);
    }
  };

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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
            <Lightbulb size={24} color="#a0a0a0" />
            AI Quant Analyst: Backtest Proposals
          </h2>
          <button 
            onClick={generateSuggestions}
            disabled={loadingSuggestions}
            style={{ 
              background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', 
              color: '#fff', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px'
            }}
          >
            {loadingSuggestions ? <Loader2 size={16} className="spin" /> : <Activity size={16} />}
            Generate New Hypotheses
          </button>
        </div>

        {suggestions.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#a0a0a0' }}>
                  <th style={{ padding: '12px' }}>Hypothesis</th>
                  <th style={{ padding: '12px' }}>Reasoning</th>
                  <th style={{ padding: '12px' }}>Params</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {suggestions.map((s, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '12px', fontWeight: 500 }}>{s.hypothesis}</td>
                    <td style={{ padding: '12px', color: '#ccc', maxWidth: '300px' }}>{s.reasoning_summary}</td>
                    <td style={{ padding: '12px', color: '#a0a0a0' }}>
                      {s.strategy} | {s.symbol} | {s.interval} | {s.days}D
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>
                      <button 
                        onClick={() => scheduleBacktest(s)}
                        style={{
                          background: 'rgba(16, 185, 129, 0.2)', border: '1px solid rgba(16, 185, 129, 0.4)',
                          color: '#10b981', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer'
                        }}
                      >
                        Schedule
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ color: '#a0a0a0', fontStyle: 'italic', padding: '20px 0' }}>
            {loadingSuggestions ? 'Generating hypotheses via Gemini...' : 'No active suggestions. Click "Generate New Hypotheses" to brainstorm with the AI.'}
          </div>
        )}

        {queue.length > 0 && (
          <div style={{ marginTop: '24px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '16px' }}>
            <h3 style={{ fontSize: '1rem', color: '#a0a0a0', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <PlayCircle size={18} /> Scheduled for Night Shift
            </h3>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {queue.map((q, idx) => (
                <div key={idx} style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 12px', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid rgba(255,255,255,0.1)' }}>
                  {q.strategy} on {q.symbol} ({q.interval}) - {q.status}
                </div>
              ))}
            </div>
          </div>
        )}
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

      <div className="glass-panel" style={{ gridColumn: 'span 3', marginTop: '20px' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 0 }}>
          <Activity size={24} color="#a0a0a0" />
          AI Trading Journal (Completed Trades)
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '20px' }}>
          {journal.length > 0 ? (
            journal.map((trade, idx) => (
              <div key={idx} style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <strong style={{ fontSize: '1.1rem' }}>{trade.symbol} - {trade.direction}</strong>
                  <span style={{ 
                    color: trade.status.includes('WIN') ? '#10b981' : '#ef4444', 
                    fontWeight: 'bold', background: trade.status.includes('WIN') ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    padding: '4px 8px', borderRadius: '4px'
                  }}>
                    {trade.status} ({trade.pnl_percent?.toFixed(2)}%)
                  </span>
                </div>
                <div style={{ color: '#a0a0a0', fontSize: '0.9rem', marginBottom: '12px', fontStyle: 'italic' }}>
                  {trade.catalyst_title} | Closed: {trade.exit_time || 'N/A'}
                </div>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '4px', fontSize: '0.85rem', lineHeight: '1.5', color: '#e5e7eb' }}>
                  <strong>Setup Context / AI Reasoning:</strong><br />
                  {trade.setup_context}
                </div>
              </div>
            ))
          ) : (
            <div style={{ color: '#a0a0a0', fontStyle: 'italic' }}>No completed trades recorded in the journal yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
