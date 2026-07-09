import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import AttendanceCalendar from './AttendanceCalendar';

export default function ClassCalendarView() {
  const [availableClasses, setAvailableClasses] = useState([]);
  const [grade, setGrade] = useState('');
  const [section, setSection] = useState('');
  
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  
  const [calendarData, setCalendarData] = useState([]);
  const [loading, setLoading] = useState(false);

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

  useEffect(() => {
    const fetchCalendar = async () => {
      if (!grade || !section) return;
      
      setLoading(true);
      try {
        const res = await api.attendance.classCalendar({
          grade: parseInt(grade),
          section,
          year,
          month
        });
        setCalendarData(res);
      } catch (err) {
        console.error('Failed to fetch calendar:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchCalendar();
  }, [grade, section, year, month]);

  const handleMonthChange = (newYear, newMonth) => {
    setYear(newYear);
    setMonth(newMonth);
  };

  const getGradientColor = (percentage) => {
    if (percentage >= 95) return 'var(--success-strong)';
    if (percentage >= 85) return 'var(--success)';
    if (percentage >= 70) return 'var(--warning)';
    return 'var(--danger)';
  };

  const renderCell = (dayData, day, dateStr) => {
    const isWeekend = new Date(dateStr).getDay() === 0 || new Date(dateStr).getDay() === 6;
    let style = {};
    let content = null;
    let textColor = 'white';
    
    if (dayData) {
      if (dayData.is_holiday) {
        style = { background: 'var(--brand)', color: 'white', borderColor: 'var(--brand-strong)' };
        content = <span style={{ fontSize: '12px' }}>Holiday</span>;
      } else if (dayData.total > 0) {
        style = { background: getGradientColor(dayData.percentage), color: 'white' };
        content = <span>{dayData.percentage}%</span>;
      }
    } else if (isWeekend) {
        style = { background: 'var(--neutral-secondary)' };
        textColor = 'var(--body-subtle)';
    } else {
        textColor = 'var(--body-subtle)';
    }

    return (
      <div key={`day-${day}`} className={`calendar-cell ${isWeekend && !dayData ? 'empty' : ''}`} style={style}>
        <div className="calendar-cell-date" style={{ color: dayData || isWeekend ? textColor : 'var(--body-subtle)' }}>{day}</div>
        <div className="calendar-cell-content" style={{ color: dayData || isWeekend ? textColor : 'inherit' }}>
          {content}
        </div>
      </div>
    );
  };

  const availableGrades = [...new Set(availableClasses.map(c => c.grade))].sort((a, b) => a - b);
  const availableSections = grade 
    ? [...new Set(availableClasses.filter(c => c.grade === parseInt(grade)).map(c => c.section))].sort()
    : [...new Set(availableClasses.map(c => c.section))].sort();

  return (
    <div>
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
        </div>
      </div>

      {grade && section ? (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '24px' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--body-subtle)' }}>Loading calendar...</div>
            ) : (
              <>
                <AttendanceCalendar 
                  year={year} 
                  month={month} 
                  data={calendarData} 
                  renderCell={renderCell}
                  onMonthChange={handleMonthChange}
                />
                
                <div className="calendar-legend">
                  <div className="legend-item">
                    <div className="legend-color" style={{ background: 'var(--success-strong)' }}></div>
                    &ge; 95%
                  </div>
                  <div className="legend-item">
                    <div className="legend-color" style={{ background: 'var(--success)' }}></div>
                    85% - 94%
                  </div>
                  <div className="legend-item">
                    <div className="legend-color" style={{ background: 'var(--warning)' }}></div>
                    70% - 84%
                  </div>
                  <div className="legend-item">
                    <div className="legend-color" style={{ background: 'var(--danger)' }}></div>
                    &lt; 70%
                  </div>
                  <div className="legend-item">
                    <div className="legend-color" style={{ background: 'var(--brand)' }}></div>
                    Holiday
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '60px', color: 'var(--body-subtle)' }}>
          <p>Select a grade and section to view the class attendance calendar.</p>
        </div>
      )}
    </div>
  );
}
