import React, { useEffect, useState } from 'react';
import { Sparkles, AlertTriangle, Info, CheckCircle2, ChevronRight } from 'lucide-react';
import { api } from '../api/client';

export default function AIAssistedDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await api.dashboard.getAdaptive();
        setData(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '40px', color: 'var(--body-subtle)', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Sparkles className="spin" size={20} color="var(--brand)" /> Generating AI insights...
      </div>
    );
  }

  if (!data || !data.widgets) return null;

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
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: '32px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Sparkles color="var(--brand)" /> Adaptive Hub
          </h1>
          <p style={{ color: 'var(--body-subtle)' }}>
            AI-curated insights prioritised by operational severity.
          </p>
        </div>
        <div style={{ fontSize: '12px', color: 'var(--body-subtle)' }}>
          Last generated: {new Date(data.generated_at).toLocaleTimeString()}
        </div>
      </div>

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
    </div>
  );
}
