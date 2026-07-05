import React, { useEffect, useState } from 'react';
import { ActivitySquare, Database, Target, Clock, MessageSquare, ShieldCheck, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';

export default function Observability() {
  const [summary, setSummary] = useState(null);
  const [failed, setFailed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningGolden, setRunningGolden] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);

  const loadData = async () => {
    try {
      const [sumRes, failRes] = await Promise.all([
        api.observability.getSummary(),
        api.observability.getFailed()
      ]);
      setSummary(sumRes);
      setFailed(failRes);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunGolden = async () => {
    setRunningGolden(true);
    try {
      await api.observability.runGolden();
      await loadData();
    } catch(err) {
      console.error(err);
    } finally {
      setRunningGolden(false);
    }
  };

  const handleClearFailed = async () => {
    try {
      await api.observability.clearFailed();
      await loadData();
    } catch(err) {
      console.error(err);
    }
  };

  const handleClearAll = async () => {
    try {
      await api.observability.clearAll();
      await loadData();
    } catch(err) {
      console.error(err);
    }
  };

  const promptClearFailed = () => {
    setConfirmAction({
      title: 'Clear Failed Queries',
      message: 'This will delete all failed chat logs. This action cannot be undone.',
      label: 'Clear Failed',
      action: handleClearFailed
    });
  };

  const promptClearAll = () => {
    setConfirmAction({
      title: 'Purge All Chat Logs',
      message: 'This will permanently delete ALL chat logs and reset observability metrics to zero. Continue?',
      label: 'Purge All Logs',
      action: handleClearAll
    });
  };

  if (loading || !summary) {
    return <div style={{ padding: '40px', color: 'var(--body-subtle)' }}>Loading observability metrics...</div>;
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: '32px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--heading)' }}>
            <ActivitySquare color="var(--success)" /> System Observability
          </h1>
          <p style={{ color: 'var(--body-subtle)' }}>
            NL2SQL pipeline metrics, performance, and golden tests.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary btn-base" style={{ color: 'var(--danger)', borderColor: 'var(--danger-soft)' }} onClick={promptClearAll}>
            Clear All Logs
          </button>
          <button className="btn btn-secondary btn-base" onClick={handleRunGolden} disabled={runningGolden}>
            {runningGolden ? 'Running Tests...' : 'Run Golden Tests Now'}
          </button>
        </div>
      </div>

      <div className="grid-layout">
        <div className="card">
          <div style={{ color: 'var(--body-subtle)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageSquare size={16} /> Total Queries
          </div>
          <div className="metric-value">{summary.total_queries}</div>
          <div style={{ fontSize: '12px', color: 'var(--body-subtle)' }}>Last 30 days</div>
        </div>
        
        <div className="card">
          <div style={{ color: 'var(--body-subtle)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Target size={16} /> SQL Success Rate
          </div>
          <div className="metric-value">{(summary.success_rate * 100).toFixed(1)}%</div>
          <div style={{ fontSize: '12px', color: summary.success_rate > 0.9 ? 'var(--success)' : 'var(--warning)' }}>
            Target: &gt;90%
          </div>
        </div>

        <div className="card">
          <div style={{ color: 'var(--body-subtle)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={16} /> Avg Latency
          </div>
          <div className="metric-value">{summary.avg_latency_ms.toFixed(0)} ms</div>
          <div style={{ fontSize: '12px', color: summary.avg_latency_ms < 5000 ? 'var(--success)' : 'var(--warning)' }}>
            Target: &lt;5s
          </div>
        </div>

        <div className="card">
          <div style={{ color: 'var(--body-subtle)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={16} /> Golden Pass Rate
          </div>
          <div className="metric-value">{summary.golden_pass_rate !== null ? (summary.golden_pass_rate * 100).toFixed(1) + '%' : 'N/A'}</div>
          <div style={{ fontSize: '12px', color: 'var(--body-subtle)' }}>
            {summary.last_run_at ? `Last run: ${new Date(summary.last_run_at).toLocaleString()}` : 'Never run'}
          </div>
        </div>
      </div>

      <div style={{ marginTop: '30px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <h3 style={{ color: 'var(--heading)' }}>Recent Failed Queries</h3>
          {failed.length > 0 && (
            <button 
              className="btn btn-secondary" 
              style={{ fontSize: '13px', padding: '6px 12px', color: 'var(--danger)', borderColor: 'var(--danger-soft)' }} 
              onClick={promptClearFailed}
            >
              <Trash2 size={14} style={{ marginRight: '6px' }} /> Clear Failed
            </button>
          )}
        </div>
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {failed.length === 0 ? (
            <div style={{ padding: '20px', color: 'var(--body-subtle)' }}>No recent failures.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Question</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {failed.map(f => (
                  <tr key={f.id}>
                    <td style={{ fontSize: '13px', color: 'var(--body-subtle)' }}>{new Date(f.timestamp).toLocaleString()}</td>
                    <td>{f.question}</td>
                    <td style={{ color: 'var(--danger)', fontSize: '13px', fontFamily: 'monospace' }}>{f.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {confirmAction && (
        <ConfirmModal
          title={confirmAction.title}
          message={confirmAction.message}
          confirmLabel={confirmAction.label}
          onConfirm={() => { confirmAction.action(); setConfirmAction(null); }}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  );
}
