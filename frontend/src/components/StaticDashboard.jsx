import React, { useEffect, useState } from 'react';
import { Users, GraduationCap, DollarSign, CalendarCheck } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';
import { api } from '../api/client';

export default function StaticDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const res = await api.dashboard.getStatic();
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
    return <div style={{ padding: '40px', color: 'var(--body-subtle)' }}>Loading overview metrics...</div>;
  }

  if (!data) return null;

  const COLORS = ['var(--success)', 'var(--warning)', 'var(--danger)', 'var(--brand)'];
  
  const feeData = [
    { name: 'Collected', value: data.fee_collected },
    { name: 'Outstanding', value: data.fee_outstanding },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Institution Overview</h1>
          <p style={{ color: 'var(--body-subtle)' }}>Standard reporting and core operational metrics.</p>
        </div>
      </div>
      
      <div className="grid-layout">
        <div className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--body-subtle)' }}>
            <Users size={20} /> Total Enrolled
          </h3>
          <p className="metric-value">{data.institution.total_students.toLocaleString()}</p>
          <p style={{ color: 'var(--success)', fontSize: '14px' }}>Active across {data.institution.active_teachers} teachers</p>
        </div>
        
        <div className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--body-subtle)' }}>
            <CalendarCheck size={20} /> Overall Attendance
          </h3>
          <p className="metric-value">{(data.attendance_trend[data.attendance_trend.length-1].value).toFixed(1)}%</p>
          <p style={{ color: 'var(--body-subtle)', fontSize: '14px' }}>Last 4 weeks avg</p>
        </div>

        <div className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--body-subtle)' }}>
            <GraduationCap size={20} /> Assignment Completion
          </h3>
          <p className="metric-value">{data.assignment_submission_rate.toFixed(1)}%</p>
          <p style={{ color: 'var(--brand)', fontSize: '14px' }}>Institution wide</p>
        </div>

        <div className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--body-subtle)' }}>
            <DollarSign size={20} /> Outstanding Fees
          </h3>
          <p className="metric-value">${data.fee_outstanding.toLocaleString()}</p>
          <p style={{ color: 'var(--warning)', fontSize: '14px' }}>Requires collection</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginTop: '24px' }}>
        
        {/* Attendance Trend Chart */}
        <div className="card">
          <h3 style={{ marginBottom: '20px' }}>Attendance Trend</h3>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.attendance_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" vertical={false} />
                <XAxis dataKey="label" stroke="var(--body-subtle)" tick={{fill: 'var(--body-subtle)'}} />
                <YAxis domain={['auto', 100]} stroke="var(--body-subtle)" tick={{fill: 'var(--body-subtle)'}} />
                <Tooltip 
                  contentStyle={{ background: 'var(--neutral-primary-soft)', border: '1px solid var(--border-default)', borderRadius: '8px' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  name="Attendance %"
                  stroke="var(--brand)" 
                  strokeWidth={3}
                  dot={{ r: 4, fill: 'var(--neutral-primary)', strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: 'var(--brand)' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Fee Collection Pie Chart */}
        <div className="card">
          <h3 style={{ marginBottom: '20px' }}>Fee Collection</h3>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={feeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {feeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ background: 'var(--neutral-primary-soft)', border: '1px solid var(--border-default)', borderRadius: '8px' }}
                  formatter={(value) => `$${value.toLocaleString()}`}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--success)'}}></div>
              <span style={{ fontSize: '14px', color: 'var(--body-subtle)' }}>Collected</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--warning)'}}></div>
              <span style={{ fontSize: '14px', color: 'var(--body-subtle)' }}>Outstanding</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
