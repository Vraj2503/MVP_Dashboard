import React, { useState, useEffect } from 'react';
import { Save, Users, Clock, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../api/client';
import StudentCalendarView from '../components/StudentCalendarView';
import ClassCalendarView from '../components/ClassCalendarView';

export default function ManageAttendance() {
  const [activeTab, setActiveTab] = useState('daily');
  const [grade, setGrade] = useState('');
  const [section, setSection] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  
  // Local state to track changes before saving
  const [attendanceState, setAttendanceState] = useState({});
  const [availableClasses, setAvailableClasses] = useState([]);

  useEffect(() => {
    const fetchClasses = async () => {
      try {
        const res = await api.academics.classes.list({ limit: 100 });
        setAvailableClasses(res.items || []);
      } catch (err) {
        console.error('Failed to fetch classes:', err);
      }
    };
    fetchClasses();
  }, []);

  const fetchAttendance = async () => {
    if (!grade || !section || !date) {
      setStudents([]);
      setAttendanceState({});
      return;
    }
    
    setLoading(true);
    try {
      const res = await api.attendance.classView({ grade, section, date });
      setStudents(res);
      
      const initialState = {};
      res.forEach(s => {
        initialState[s.student_id] = s.status || null;
      });
      setAttendanceState(initialState);
    } catch (err) {
      console.error('Failed to fetch class attendance:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAttendance();
  }, [grade, section, date]);

  const handleStatusChange = (studentId, status) => {
    setAttendanceState(prev => ({
      ...prev,
      [studentId]: status
    }));
  };

  const handleSaveAll = async () => {
    const recordsToUpdate = Object.entries(attendanceState)
      .filter(([id, status]) => status !== null)
      .map(([id, status]) => ({
        student_id: parseInt(id),
        status
      }));
      
    if (recordsToUpdate.length === 0) return;

    setSaving(true);
    try {
      await api.attendance.bulkSave({
        date,
        grade: parseInt(grade),
        section,
        records: recordsToUpdate
      });
      // No re-fetch needed — local attendanceState already reflects the saved values
    } catch (err) {
      console.error('Failed to save attendance:', err);
      // Re-fetch on error to restore server state
      await fetchAttendance();
    } finally {
      setSaving(false);
    }
  };

  const handleMarkAllPresent = () => {
    const newState = { ...attendanceState };
    students.forEach(s => {
      newState[s.student_id] = 'Present';
    });
    setAttendanceState(newState);
  };

  const handleMarkDateAsHoliday = () => {
    const newState = { ...attendanceState };
    students.forEach(s => {
      newState[s.student_id] = 'Holiday';
    });
    setAttendanceState(newState);
  };

  // Compute summary stats
  const stats = {
    present: Object.values(attendanceState).filter(s => s === 'Present').length,
    absent: Object.values(attendanceState).filter(s => s === 'Absent').length,
    total: students.length
  };

  const isHolidayDay = students.length > 0 && Object.keys(attendanceState).length > 0 && students.every(s => attendanceState[s.student_id] === 'Holiday');

  const availableGrades = [...new Set(availableClasses.map(c => c.grade))].sort((a, b) => a - b);
  const availableSections = grade 
    ? [...new Set(availableClasses.filter(c => c.grade === parseInt(grade)).map(c => c.section))].sort()
    : [...new Set(availableClasses.map(c => c.section))].sort();

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>Manage Attendance</h2>
          <p style={{ color: 'var(--body-subtle)' }}>Record and update daily attendance by class</p>
        </div>
      </div>

      <div className="attendance-tabs">
        <button 
          className={`attendance-tab ${activeTab === 'daily' ? 'active' : ''}`}
          onClick={() => setActiveTab('daily')}
        >
          Daily View
        </button>
        <button 
          className={`attendance-tab ${activeTab === 'student' ? 'active' : ''}`}
          onClick={() => setActiveTab('student')}
        >
          Student Calendar
        </button>
        <button 
          className={`attendance-tab ${activeTab === 'class' ? 'active' : ''}`}
          onClick={() => setActiveTab('class')}
        >
          Class Calendar
        </button>
      </div>

      {activeTab === 'daily' && (
        <>
          <div className="card" style={{ marginBottom: '24px' }}>
        <div className="search-filter-bar" style={{ marginBottom: 0 }}>
          <div>
            <label className="form-label">Grade</label>
            <select className="form-select" value={grade} onChange={e => setGrade(e.target.value)} style={{ width: '150px' }}>
              <option value="">Select Grade...</option>
              {availableGrades.map(g => (
                <option key={g} value={g}>Grade {g}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Section</label>
            <select className="form-select" value={section} onChange={e => setSection(e.target.value)} style={{ width: '150px' }}>
              <option value="">Select Section...</option>
              {availableSections.map(s => (
                <option key={s} value={s}>Section {s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label">Date</label>
            <input 
              type="date" 
              className="form-input" 
              value={date} 
              onChange={e => setDate(e.target.value)}
              style={{ width: '200px' }}
            />
          </div>
        </div>
      </div>

      {students.length > 0 && (
        <div className="attendance-summary-bar">
          <div className="summary-stats">
            <div className="stat-item">
              <Users size={18} color="var(--brand)" />
              <span>Total: {stats.total}</span>
            </div>
            <div className="stat-item" style={{ color: 'var(--success-strong)' }}>
              <CheckCircle size={18} />
              <span>Present: {stats.present}</span>
            </div>
            <div className="stat-item" style={{ color: 'var(--danger-strong)' }}>
              <AlertCircle size={18} />
              <span>Absent: {stats.absent}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={handleMarkAllPresent}
              disabled={stats.total === 0}
            >
              <CheckCircle size={16} />
              Mark All Present
            </button>
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={handleMarkDateAsHoliday}
              disabled={stats.total === 0}
            >
              <Clock size={16} />
              Mark as Holiday
            </button>
            <button 
              className="btn btn-primary" 
              onClick={handleSaveAll}
              disabled={saving || stats.total === 0}
            >
              <Save size={18} />
              {saving ? 'Saving...' : 'Save Attendance'}
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {isHolidayDay && (
          <div style={{
            backgroundColor: 'var(--brand-softer)',
            color: 'var(--brand-strong)',
            padding: '16px',
            margin: '24px 24px 0 24px',
            borderRadius: 'var(--radius-base)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            border: '1px solid var(--border-brand-subtle)'
          }}>
            <Clock size={20} />
            <span style={{ fontWeight: 500 }}>This date is marked as a Holiday. Students are not required to attend.</span>
          </div>
        )}
        <div style={{ padding: '24px', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Student Name</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={2} style={{ textAlign: 'center', padding: '40px', color: 'var(--body-subtle)' }}>
                    Loading attendance...
                  </td>
                </tr>
              ) : students.length > 0 ? (
                students.map(student => (
                  <tr key={student.student_id}>
                    <td style={{ fontWeight: '500' }}>{student.student_name}</td>
                    <td>
                      <div className="status-toggle-group">
                        <button 
                          className={`status-toggle present ${attendanceState[student.student_id] === 'Present' ? 'active' : ''}`}
                          onClick={() => handleStatusChange(student.student_id, 'Present')}
                          disabled={isHolidayDay}
                          style={isHolidayDay ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
                        >
                          Present
                        </button>
                        <button 
                          className={`status-toggle absent ${attendanceState[student.student_id] === 'Absent' ? 'active' : ''}`}
                          onClick={() => handleStatusChange(student.student_id, 'Absent')}
                          disabled={isHolidayDay}
                          style={isHolidayDay ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
                        >
                          Absent
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={2} style={{ textAlign: 'center', padding: '40px', color: 'var(--body-subtle)' }}>
                    {grade && section ? 'No students found in this class.' : 'Select a grade and section to view students.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}

      {activeTab === 'student' && <StudentCalendarView />}
      {activeTab === 'class' && <ClassCalendarView />}
    </div>
  );
}
