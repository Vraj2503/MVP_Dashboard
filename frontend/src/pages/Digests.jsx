import React, { useEffect, useState } from 'react';
import { FileText, Sparkles, Calendar, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';

export default function Digests() {
  const [digests, setDigests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  
  const [preset, setPreset] = useState('14'); // '14', '30', '90', 'custom'
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const loadDigests = async () => {
    try {
      const res = await api.digests.list();
      setDigests(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDigests();
  }, []);

  const handleGenerate = async () => {
    let s = startDate;
    let e = endDate;
    if (preset !== 'custom') {
      const d = new Date();
      e = d.toISOString().split('T')[0];
      const days = parseInt(preset, 10) || 14;
      d.setDate(d.getDate() - days);
      s = d.toISOString().split('T')[0];
    }
    
    if (!s || !e) return;

    setGenerating(true);
    try {
      await api.digests.generate(s, e);
      await loadDigests();
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.digests.delete(id);
      await loadDigests();
    } catch (err) {
      console.error(err);
    }
  };

  const handleClearAll = async () => {
    try {
      await api.digests.clearAll();
      await loadDigests();
    } catch (err) {
      console.error(err);
    }
  };

  const promptDelete = (id) => {
    setConfirmAction({
      title: 'Delete Digest',
      message: 'Are you sure you want to delete this digest? This action cannot be undone.',
      label: 'Delete',
      action: () => handleDelete(id)
    });
  };

  const promptClearAll = () => {
    setConfirmAction({
      title: 'Clear All Digests',
      message: 'This will permanently delete all periodic digests. Continue?',
      label: 'Clear All',
      action: handleClearAll
    });
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px' }}>
        <div>
          <h1 style={{ fontSize: '32px', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--heading)' }}>
            <FileText color="var(--brand)" /> Periodic Digests
          </h1>
          <p style={{ color: 'var(--body-subtle)' }}>
            Narrative summaries of institutional performance.
          </p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', background: 'var(--white)', padding: '12px 20px', borderRadius: '12px', border: '1px solid var(--border-default)', boxShadow: '0 2px 8px rgba(0,0,0,0.02)', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--heading)' }}>
            <Calendar size={18} color="var(--brand)" />
            <span style={{ fontWeight: '500', fontSize: '14px' }}>Period:</span>
          </div>
          
          <select 
            value={preset} 
            onChange={(e) => setPreset(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-default)', outline: 'none', background: 'var(--neutral-tertiary-soft)', fontSize: '14px' }}
          >
            <option value="14">Last 14 Days</option>
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
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px', marginLeft: 'auto' }}>
            {digests.length > 0 && (
              <button className="btn btn-secondary btn-base" style={{ color: 'var(--danger)', borderColor: 'var(--danger-soft)' }} onClick={promptClearAll}>
                Clear All
              </button>
            )}
            <button 
              className="btn btn-primary btn-base" 
              onClick={handleGenerate} 
              disabled={generating || (preset === 'custom' && (!startDate || !endDate))}
            >
              {generating ? 'Generating...' : 'Generate New Digest'}
            </button>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {loading ? (
          <div>Loading digests...</div>
        ) : digests.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--body-subtle)' }}>
            No digests available. Generate one.
          </div>
        ) : (
          digests.map(d => (
            <div key={d.id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px', borderBottom: '1px solid var(--border-default)', paddingBottom: '15px' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--heading)' }}>
                  <Calendar size={18} />
                  Period: {new Date(d.period_start).toLocaleDateString()} - {new Date(d.period_end).toLocaleDateString()}
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ color: 'var(--body-subtle)', fontSize: '14px' }}>Generated: {new Date(d.created_at).toLocaleString()}</span>
                  <button 
                    className="btn btn-icon" 
                    onClick={() => promptDelete(d.id)}
                    title="Delete digest"
                    style={{ color: 'var(--body-subtle)', padding: '4px' }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              
              <div style={{ background: 'var(--brand-softer)', padding: '20px', borderRadius: '12px', marginBottom: '20px', border: '1px solid var(--border-brand-subtle)' }}>
                <div className="badge badge-brand" style={{ marginBottom: '12px' }}>
                  <Sparkles size={14} /> Executive Summary
                </div>
                <p style={{ fontSize: '16px', lineHeight: '1.6', color: 'var(--fg-brand-strong)' }}>{d.content.narrative}</p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
                <div style={{ background: 'var(--neutral-tertiary-soft)', padding: '15px', borderRadius: '8px', border: '1px solid var(--border-default)' }}>
                  <div style={{ color: 'var(--body-subtle)', fontSize: '14px', marginBottom: '5px' }}>Attendance Delta</div>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: d.content.attendance?.delta < 0 ? 'var(--danger)' : 'var(--success)' }}>
                    {d.content.attendance?.delta > 0 ? '+' : ''}{d.content.attendance?.delta}%
                  </div>
                </div>
                
                <div style={{ background: 'var(--neutral-tertiary-soft)', padding: '15px', borderRadius: '8px', border: '1px solid var(--border-default)' }}>
                  <div style={{ color: 'var(--body-subtle)', fontSize: '14px', marginBottom: '5px' }}>New At-Risk Students</div>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--heading)' }}>{d.content.new_at_risk?.length || 0}</div>
                </div>

                <div style={{ background: 'var(--neutral-tertiary-soft)', padding: '15px', borderRadius: '8px', border: '1px solid var(--border-default)' }}>
                  <div style={{ color: 'var(--body-subtle)', fontSize: '14px', marginBottom: '5px' }}>Outstanding Fees</div>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--warning)' }}>
                    ${(d.content.fees?.outstanding || 0).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          ))
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
