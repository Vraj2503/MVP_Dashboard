import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Sparkles, Activity, Bell, FileText, ActivitySquare, GraduationCap, Users, ClipboardCheck } from 'lucide-react';

import StaticDashboard from './components/StaticDashboard';
import AIAssistedDashboard from './components/AIAssistedDashboard';
import Chatbot from './components/Chatbot';
import Digests from './pages/Digests';
import Observability from './pages/Observability';
import Alerts from './pages/Alerts';
import ManageAcademics from './pages/ManageAcademics';
import ManageStudents from './pages/ManageStudents';
import ManageAttendance from './pages/ManageAttendance';
import { api } from './api/client';

function Navigation() {
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const res = await api.alerts.unreadCount();
        setUnreadCount(res.count || 0);
      } catch (err) {
        console.error(err);
      }
    };
    fetchCount();
    const interval = setInterval(fetchCount, 60000); // poll every 60s
    return () => clearInterval(interval);
  }, []);
  
  const dashboardNavItems = [
    { path: '/', label: 'Overview', icon: LayoutDashboard },
    { path: '/ai-assisted', label: 'Adaptive Hub', icon: Sparkles },
    { path: '/alerts', label: 'Alerts', icon: Bell, badge: unreadCount },
    { path: '/digests', label: 'Digests', icon: FileText },
    { path: '/observability', label: 'Observability', icon: ActivitySquare },
  ];

  const managementNavItems = [
    { path: '/academics', label: 'Academics', icon: GraduationCap },
    { path: '/students', label: 'Students', icon: Users },
    { path: '/attendance', label: 'Attendance', icon: ClipboardCheck },
  ];

  const renderNavItem = (item) => {
    const Icon = item.icon;
    return (
      <Link 
        key={item.path}
        to={item.path} 
        className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
      >
        <span style={{ position: 'relative', display: 'inline-flex' }}>
          <Icon size={20} />
          {item.badge > 0 && (
            <span className="nav-badge">{item.badge > 99 ? '99+' : item.badge}</span>
          )}
        </span>
        {item.label}
      </Link>
    );
  };

  return (
    <nav className="sidebar-nav">
      {dashboardNavItems.map(renderNavItem)}
      <div className="nav-section-label">Management</div>
      {managementNavItems.map(renderNavItem)}
    </nav>
  );
}

function App() {
  const [showChat, setShowChat] = useState(false);

  return (
    <Router>
      <div className="dashboard-container">
        
        {/* Sidebar */}
        <aside className="dashboard-sidebar">
          <div className="sidebar-header">
            <h1>Symmetry</h1>
            <p style={{ color: 'var(--body-subtle)', fontSize: '14px' }}>School Operations Hub</p>
          </div>
          <Navigation />
          
          <div style={{ marginTop: 'auto', padding: '20px 0' }}>
            <div className="card" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'var(--brand)', color: 'var(--white)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '500' }}>AD</div>
                <div>
                  <p style={{ fontWeight: '500', fontSize: '14px', color: 'var(--heading)' }}>Admin User</p>
                  <p style={{ color: 'var(--body-subtle)', fontSize: '12px' }}>Institution Level</p>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="dashboard-main">
          <Routes>
            <Route path="/" element={<StaticDashboard />} />
            <Route path="/ai-assisted" element={<AIAssistedDashboard />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/digests" element={<Digests />} />
            <Route path="/observability" element={<Observability />} />
            <Route path="/academics" element={<ManageAcademics />} />
            <Route path="/students" element={<ManageStudents />} />
            <Route path="/attendance" element={<ManageAttendance />} />
          </Routes>
        </main>

        {/* Floating Chatbot Toggle */}
        <button 
          onClick={() => setShowChat(!showChat)}
          title="NL2SQL Copilot"
          style={{
            position: 'fixed',
            bottom: '32px',
            right: showChat ? '432px' : '32px',
            background: 'var(--brand)',
            color: 'var(--white)',
            border: 'none',
            borderRadius: 'var(--radius-pill)',
            width: '56px',
            height: '56px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: 'var(--shadow-lg)',
            transition: 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
            zIndex: 1001
          }}
        >
          {showChat ? <span style={{fontSize: '24px'}}>✕</span> : <Sparkles size={24} />}
        </button>

        {showChat && <Chatbot />}
      </div>
    </Router>
  );
}

export default App;
