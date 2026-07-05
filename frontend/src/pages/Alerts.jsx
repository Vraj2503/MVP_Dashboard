import React, { useEffect, useState, useCallback } from 'react';
import { Bell, ShieldAlert, AlertTriangle, Info, CheckCircle2, Search, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';

const SEVERITY_CONFIG = {
  critical: { icon: ShieldAlert, color: 'var(--danger)', bg: 'var(--danger-soft)', label: 'Critical' },
  high:     { icon: AlertTriangle, color: 'var(--danger)', bg: 'var(--danger-soft)', label: 'High' },
  medium:   { icon: AlertTriangle, color: 'var(--warning)', bg: 'var(--warning-soft, rgba(245, 158, 11, 0.1))', label: 'Medium' },
  low:      { icon: Info, color: 'var(--brand)', bg: 'var(--brand-softer)', label: 'Low' },
};

const STATUS_TABS = ['all', 'open', 'ack', 'dismissed'];

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [activeStatus, setActiveStatus] = useState('open');
  const [severityFilter, setSeverityFilter] = useState('');
  const [confirmAction, setConfirmAction] = useState(null);

  const loadAlerts = useCallback(async () => {
    try {
      const filters = {};
      if (activeStatus !== 'all') filters.status = activeStatus;
      if (severityFilter) filters.severity = severityFilter;
      const res = await api.alerts.list(filters);
      setAlerts(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [activeStatus, severityFilter]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.alerts.scan();
      await loadAlerts();
    } catch (err) {
      console.error(err);
    } finally {
      setScanning(false);
    }
  };

  const handleStatusUpdate = async (alertId, newStatus) => {
    try {
      await api.alerts.updateStatus(alertId, newStatus);
      await loadAlerts();
    } catch (err) {
      console.error(err);
    }
  };

  const openCount = alerts.filter(a => a.status === 'open').length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: '32px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--heading)' }}>
            <Bell color="var(--warning)" /> Alerts
            {openCount > 0 && (
              <span className="alert-badge-large">{openCount}</span>
            )}
          </h1>
          <p style={{ color: 'var(--body-subtle)' }}>
            System-generated anomalies and threshold violations.
          </p>
        </div>
        <button className="btn btn-primary btn-base" onClick={handleScan} disabled={scanning}>
          <RefreshCw size={16} className={scanning ? 'spin' : ''} />
          {scanning ? 'Scanning...' : 'Run Alert Scan'}
        </button>
      </div>

      {/* Filters */}
      <div className="alert-filters">
        <div className="alert-status-tabs">
          {STATUS_TABS.map(tab => (
            <button
              key={tab}
              className={`alert-tab ${activeStatus === tab ? 'active' : ''}`}
              onClick={() => setActiveStatus(tab)}
            >
              {tab === 'all' ? 'All' : tab === 'ack' ? 'Acknowledged' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
        <select
          className="alert-severity-select"
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Alert List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '20px' }}>
        {loading ? (
          <div style={{ padding: '40px', color: 'var(--body-subtle)', textAlign: 'center' }}>Loading alerts...</div>
        ) : alerts.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px 40px', color: 'var(--body-subtle)' }}>
            <CheckCircle2 size={48} color="var(--success)" style={{ marginBottom: '16px', opacity: 0.5 }} />
            <h3 style={{ color: 'var(--heading)', marginBottom: '8px' }}>All Clear</h3>
            <p>No alerts match your current filters. The system is operating normally.</p>
          </div>
        ) : (
          alerts.map(alert => {
            const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low;
            const Icon = config.icon;
            return (
              <div
                key={alert.id}
                className="card alert-card"
                style={{ borderLeft: `4px solid ${config.color}`, opacity: alert.status === 'dismissed' ? 0.6 : 1 }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                      <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: config.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Icon size={18} color={config.color} />
                      </div>
                      <span className={`badge badge-${alert.severity === 'critical' || alert.severity === 'high' ? 'danger' : alert.severity === 'medium' ? 'warning' : 'brand'}`}>
                        {config.label}
                      </span>
                      <span className="badge" style={{ background: 'var(--neutral-tertiary-soft)', color: 'var(--body-subtle)', fontSize: '11px' }}>
                        {alert.type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p style={{ fontSize: '15px', lineHeight: '1.6', color: 'var(--body)', marginBottom: '10px' }}>
                      {alert.message}
                    </p>
                    {alert.suggested_action && (
                      <div style={{ background: 'var(--brand-softer)', padding: '12px 16px', borderRadius: '8px', fontSize: '13px', color: 'var(--fg-brand-strong)', border: '1px solid var(--border-brand-subtle)' }}>
                        <strong>Suggested Action:</strong> {alert.suggested_action}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '10px', minWidth: '140px' }}>
                    <span style={{ fontSize: '12px', color: 'var(--body-subtle)' }}>
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                    {alert.status === 'open' && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          className="btn btn-secondary"
                          style={{ fontSize: '12px', padding: '4px 12px' }}
                          onClick={() => handleStatusUpdate(alert.id, 'ack')}
                        >
                          Acknowledge
                        </button>
                        <button
                          className="btn"
                          style={{ fontSize: '12px', padding: '4px 12px', background: 'transparent', border: '1px solid var(--border-default)', color: 'var(--body-subtle)' }}
                          onClick={() => handleStatusUpdate(alert.id, 'dismissed')}
                        >
                          Dismiss
                        </button>
                      </div>
                    )}
                    {alert.status === 'ack' && (
                      <span className="badge" style={{ background: 'var(--brand-softer)', color: 'var(--brand)' }}>Acknowledged</span>
                    )}
                    {alert.status === 'dismissed' && (
                      <span className="badge" style={{ background: 'var(--neutral-tertiary-soft)', color: 'var(--body-subtle)' }}>Dismissed</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
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
