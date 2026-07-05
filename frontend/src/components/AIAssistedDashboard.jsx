import React, { useEffect, useState } from 'react';
import { Sparkles, AlertTriangle, Info, CheckCircle2, ChevronRight, Calendar } from 'lucide-react';
import { api } from '../api/client';

export default function AIAssistedDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [preset, setPreset] = useState('all'); // 'all', '30', '90', 'custom'
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const loadData = async (start, end) => {
    setLoading(true);
    try {
      const res = await api.dashboard.getAdaptive(start, end);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let start = '';
    let end = '';
    if (preset === '30') {
      const d = new Date();
      end = d.toISOString().split('T')[0];
      d.setDate(d.getDate() - 30);
      start = d.toISOString().split('T')[0];
      setStartDate(start);
      setEndDate(end);
      loadData(start, end);
    } else if (preset === '90') {
      const d = new Date();
      end = d.toISOString().split('T')[0];
      d.setDate(d.getDate() - 90);
      start = d.toISOString().split('T')[0];
      setStartDate(start);
      setEndDate(end);
      loadData(start, end);
    } else if (preset === 'all') {
      setStartDate('');
      setEndDate('');
      loadData('', '');
    }
  }, [preset]);

  const handleCustomApply = () => {
    if (startDate && endDate) {
      loadData(startDate, endDate);
    }
  };

  const renderIcon = (severity) => {
    switch(severity) {
      case 'danger': return <AlertTriangle color="var(--danger)" />;
      case 'warn': return <AlertTriangle color="var(--warning)" />;
      case 'ok': return <CheckCircle2 color="var(--success)" />;
      default: return <Info color="var(--brand)" />;
    }
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px' }}>
        <div>
          <h1 style={{ fontSize: '32px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Sparkles color="var(--brand)" /> Adaptive Hub
          </h1>
          <p style={{ color: 'var(--body-subtle)' }}>
            AI-curated insights prioritised by operational severity.
          </p>
        </div>
        
        {/* Timeframe Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', background: 'var(--white)', padding: '12px 20px', borderRadius: '12px', border: '1px solid var(--border-default)', boxShadow: '0 2px 8px rgba(0,0,0,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--heading)' }}>
            <Calendar size={18} color="var(--brand)" />
            <span style={{ fontWeight: '500', fontSize: '14px' }}>Timeframe:</span>
          </div>
          
          <select 
            value={preset} 
            onChange={(e) => setPreset(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-default)', outline: 'none', background: 'var(--neutral-tertiary-soft)', fontSize: '14px' }}
          >
            <option value="all">All Time</option>
            <option value="30">Last 30 Days</option>
            <option value="90">Last 3 Months</option>
            <option value="custom">Custom Range</option>
          </select>

          {preset === 'custom' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <input 
                type="date" 
                value={startDate} 
                onChange={(e) => setStartDate(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border-default)', outline: 'none', fontSize: '13px' }}
              />
              <span style={{ color: 'var(--body-subtle)' }}>to</span>
              <input 
                type="date" 
                value={endDate} 
                onChange={(e) => setEndDate(e.target.value)}
                style={{ padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border-default)', outline: 'none', fontSize: '13px' }}
              />
              <button 
                onClick={handleCustomApply}
                disabled={!startDate || !endDate}
                style={{ padding: '6px 12px', background: 'var(--brand)', color: 'var(--white)', border: 'none', borderRadius: '6px', cursor: (!startDate || !endDate) ? 'not-allowed' : 'pointer', fontSize: '13px', fontWeight: '500', opacity: (!startDate || !endDate) ? 0.5 : 1 }}
              >
                Apply
              </button>
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '40px', color: 'var(--body-subtle)', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Sparkles className="spin" size={20} color="var(--brand)" /> Generating AI insights...
        </div>
      ) : (!data || !data.widgets) ? null : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {data.widgets.map((widget) => {
            let borderColor = 'var(--border-default)';
            if (widget.severity === 'danger') borderColor = 'var(--danger)';
            if (widget.severity === 'warn') borderColor = 'var(--warning)';
            if (widget.severity === 'ok') borderColor = 'var(--success)';
            
            return (
              <div key={widget.id} className="card ai-widget-card" style={{ borderLeft: `4px solid ${borderColor}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  
                  <div style={{ flex: '1', paddingRight: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px' }}>
                      {renderIcon(widget.severity)}
                      <h3 style={{ fontSize: '20px', color: 'var(--heading)' }}>{widget.title}</h3>
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '15px', marginBottom: '15px' }}>
                      <span className="metric-value">{widget.primary_value}</span>
                      <span style={{ color: 'var(--body-subtle)', fontSize: '16px' }}>{widget.secondary}</span>
                    </div>
                    
                    {widget.rationale && (
                      <p style={{ fontSize: '14px', color: 'var(--body-subtle)', marginBottom: '15px', fontStyle: 'italic' }}>
                        System Note: {widget.rationale}
                      </p>
                    )}
                  </div>
                  
                  <div style={{ flex: '1.5', background: 'var(--neutral-tertiary-soft)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-default)' }}>
                    <div className="badge badge-brand" style={{ marginBottom: '12px' }}>
                      <Sparkles size={14} /> AI Narrative Insight
                    </div>
                    <p style={{ fontSize: '15px', lineHeight: '1.6', color: 'var(--body)', marginBottom: widget.breakdown || (widget.recommendations && widget.recommendations.length > 0) ? '16px' : '0' }}>
                      {widget.narrative}
                    </p>
                    
                    {widget.breakdown && (
                      <div style={{ marginBottom: widget.recommendations && widget.recommendations.length > 0 ? '16px' : '0' }}>
                        <div style={{ fontSize: '12px', color: 'var(--body-subtle)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Breakdown</div>
                        <div style={{ fontSize: '14px', color: 'var(--heading)', background: 'var(--white)', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-default)' }}>
                          {widget.breakdown}
                        </div>
                      </div>
                    )}

                    {widget.recommendations && widget.recommendations.length > 0 && (
                      <div>
                        <div style={{ fontSize: '12px', color: 'var(--body-subtle)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>Actionable Recommendations</div>
                        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {widget.recommendations.map((rec, i) => (
                            <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '14px', color: 'var(--body)' }}>
                              <ChevronRight size={16} color="var(--brand)" style={{ marginTop: '2px', flexShrink: 0 }} />
                              {rec}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
