import React, { useState, useRef, useEffect } from 'react';
import { Send, Terminal, ThumbsUp, ThumbsDown, ChevronDown, ChevronRight, CheckCircle2 } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';

const COLORS = ['var(--brand)', 'var(--success)', 'var(--warning)', 'var(--danger)', '#8b5cf6'];

export default function Chatbot() {
  const [messages, setMessages] = useState([
    { type: 'system', text: 'NL2SQL Copilot initialized. Ask a question about the school data.' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    setInput('');
    setMessages(prev => [...prev, { type: 'user', text: text }]);
    setIsLoading(true);

    try {
      const res = await api.chat.send(text, sessionId);
      if (res.session_id && !sessionId) {
        setSessionId(res.session_id);
      }
      setMessages(prev => [...prev, { 
        type: 'bot', 
        ...res 
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { 
        type: 'bot', 
        answer: `Error: ${err.message}`, 
        error: true 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    await sendMessage(input);
  };

  const handleFeedback = async (logId, value, msgIndex) => {
    if (!logId) return;
    try {
      await api.chat.feedback(logId, value);
      const newMsgs = [...messages];
      newMsgs[msgIndex].feedbackSent = true;
      setMessages(newMsgs);
    } catch(err) {
      console.error("Failed to send feedback", err);
    }
  };

  const renderChart = (msg) => {
    if (!msg.rows || msg.rows.length === 0 || !msg.columns) return null;
    const { chart_hint, rows, columns } = msg;

    if (chart_hint === 'kpi') {
      const val = rows[0][columns[0]];
      const label = columns[0];
      return (
        <div className="chatbot-kpi">
          <div className="chatbot-kpi-val">{typeof val === 'number' ? val.toLocaleString() : val}</div>
          <div className="chatbot-kpi-label">{label.replace(/_/g, ' ')}</div>
        </div>
      );
    }

    if (chart_hint === 'line' || chart_hint === 'bar') {
      const dateCol = columns.find(c => /(date|time|day|week|month|year|period|semester|term)/i.test(c)) || columns[0];
      const numCols = columns.filter(c => c !== dateCol && typeof rows[0][c] === 'number');
      if (numCols.length === 0) return <ChatbotTable msg={msg} />;

      const ChartComp = chart_hint === 'line' ? LineChart : BarChart;
      const DataComp = chart_hint === 'line' ? Line : Bar;

      return (
        <div className="chatbot-chart-container">
          <ResponsiveContainer width="100%" height={250}>
            <ChartComp data={rows} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" vertical={false} />
              <XAxis dataKey={dateCol} stroke="var(--body-subtle)" fontSize={11} tickFormatter={(val) => {
                if (val instanceof Date) return val.toLocaleDateString();
                if (typeof val === 'string' && val.includes('T')) return new Date(val).toLocaleDateString();
                return val;
              }} />
              <YAxis stroke="var(--body-subtle)" fontSize={11} />
              <Tooltip contentStyle={{ background: 'var(--neutral-primary-soft)', border: '1px solid var(--border-default)', borderRadius: '8px', fontSize: '12px' }} />
              {numCols.map((c, i) => (
                <DataComp 
                  key={c}
                  type="monotone" 
                  dataKey={c} 
                  name={c.replace(/_/g, ' ')}
                  stroke={COLORS[i % COLORS.length]} 
                  fill={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                />
              ))}
            </ChartComp>
          </ResponsiveContainer>
        </div>
      );
    }

    if (chart_hint === 'pie') {
      const catCol = columns.find(c => typeof rows[0][c] === 'string') || columns[0];
      const numCol = columns.find(c => typeof rows[0][c] === 'number') || columns[1];
      if (!catCol || !numCol) return <ChatbotTable msg={msg} />;

      return (
        <div className="chatbot-chart-container" style={{ display: 'flex', alignItems: 'center' }}>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={rows}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={80}
                paddingAngle={2}
                dataKey={numCol}
                nameKey={catCol}
              >
                {rows.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--neutral-primary-soft)', border: '1px solid var(--border-default)', borderRadius: '8px', fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ paddingRight: '20px' }}>
            {rows.map((r, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', marginBottom: '4px', color: 'var(--body)' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: COLORS[i % COLORS.length] }}></div>
                {r[catCol]}
              </div>
            ))}
          </div>
        </div>
      );
    }

    return <ChatbotTable msg={msg} />;
  };

  const ChatbotTable = ({ msg }) => {
    const [expanded, setExpanded] = useState(false);
    const hasMore = msg.rows.length > 5;
    const displayedRows = expanded ? msg.rows : msg.rows.slice(0, 5);

    return (
      <div className="chatbot-table-container">
        <table>
          <thead>
            <tr>
              {msg.columns.map(c => <th key={c}>{c.replace(/_/g, ' ')}</th>)}
            </tr>
          </thead>
          <tbody>
            {displayedRows.map((r, i) => (
              <tr key={i}>
                {msg.columns.map(c => <td key={c}>{r[c]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {hasMore && (
          <div 
            className="chatbot-table-footer" 
            onClick={() => setExpanded(!expanded)}
            style={{ cursor: 'pointer', color: 'var(--brand)', userSelect: 'none' }}
          >
            {expanded ? 'Show less' : `Show all ${msg.rows.length} rows`}
          </div>
        )}
      </div>
    );
  };

  const SqlPreview = ({ sql }) => {
    const [expanded, setExpanded] = useState(false);
    return (
      <div className="chatbot-sql-preview">
        <div className="chatbot-sql-header" onClick={() => setExpanded(!expanded)}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span>Generated SQL</span>
        </div>
        {expanded && (
          <pre className="chatbot-sql-content">
            {sql}
          </pre>
        )}
      </div>
    );
  };

  return (
    <div className="chatbot-overlay" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ background: 'var(--neutral-tertiary-soft)', padding: '15px 20px', borderBottom: '1px solid var(--border-default)' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Terminal size={18} /> Data Copilot
        </h3>
      </div>
      
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} style={{
            alignSelf: msg.type === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: msg.type === 'user' ? '80%' : '90%'
          }}>
            {msg.type === 'system' && (
              <div style={{ fontSize: '12px', color: 'var(--body-subtle)', textAlign: 'center', margin: '10px 0' }}>
                {msg.text}
              </div>
            )}
            
            {msg.type === 'user' && (
              <div style={{ 
                background: 'var(--brand)', 
                color: 'var(--white)', 
                padding: '10px 15px', 
                borderRadius: '15px 15px 0 15px',
                marginBottom: '10px'
              }}>
                {msg.text}
              </div>
            )}

            {msg.type === 'bot' && (
              <div style={{
                background: msg.error ? 'var(--danger-soft)' : 'var(--neutral-secondary-medium)',
                border: `1px solid ${msg.error ? 'var(--border-danger)' : 'var(--border-default)'}`,
                padding: '15px',
                borderRadius: '15px 15px 15px 0',
                marginBottom: '10px',
                color: 'var(--body)'
              }}>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '14px', lineHeight: '1.5' }}>
                  {msg.answer}
                </div>

                {msg.rows && msg.rows.length > 0 && (
                  <div style={{ marginTop: '15px' }}>
                    {renderChart(msg)}
                  </div>
                )}

                {msg.sql && (
                  <SqlPreview sql={msg.sql} />
                )}

                {msg.choices && msg.choices.length > 0 && (
                  <div className="chatbot-choices">
                    {msg.choices.map((choice, cidx) => (
                      <button
                        key={cidx}
                        className="chatbot-choice-chip"
                        onClick={() => sendMessage(choice)}
                        disabled={isLoading}
                      >
                        {choice}
                      </button>
                    ))}
                  </div>
                )}

                {msg.log_id && !msg.feedbackSent && (
                  <div style={{ display: 'flex', gap: '10px', marginTop: '15px', justifyContent: 'flex-end' }}>
                    <button onClick={() => handleFeedback(msg.log_id, 1, idx)} title="Good response" style={{ background: 'none', border: 'none', color: 'var(--body-subtle)', cursor: 'pointer' }}>
                      <ThumbsUp size={16} />
                    </button>
                    <button onClick={() => handleFeedback(msg.log_id, -1, idx)} title="Bad response" style={{ background: 'none', border: 'none', color: 'var(--body-subtle)', cursor: 'pointer' }}>
                      <ThumbsDown size={16} />
                    </button>
                  </div>
                )}
                {msg.feedbackSent && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--success)', justifyContent: 'flex-end', marginTop: '10px' }}>
                    <CheckCircle2 size={12} /> Feedback recorded.
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="chatbot-typing">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="chat-input-area">
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a follow-up..." 
          className="chat-input"
          disabled={isLoading}
        />
        <button type="submit" className="btn btn-primary" style={{ padding: '0 16px', borderRadius: 'var(--radius-base)' }} disabled={isLoading || !input.trim()}>
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
