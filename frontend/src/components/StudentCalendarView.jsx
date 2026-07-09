import React, { useState, useEffect, useRef } from 'react';
import { Search } from 'lucide-react';
import { api } from '../api/client';
import AttendanceCalendar from './AttendanceCalendar';

export default function StudentCalendarView() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  
  const [selectedStudent, setSelectedStudent] = useState(null);
  
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  
  const [calendarData, setCalendarData] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const searchTimeout = useRef(null);

  // Debounced search
  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults([]);
      return;
    }
    
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    
    searchTimeout.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await api.students.search(searchQuery);
        setSearchResults(res.items || []);
        setShowDropdown(true);
      } catch (err) {
        console.error('Failed to search students:', err);
      } finally {
        setIsSearching(false);
      }
    }, 300);
    
    return () => clearTimeout(searchTimeout.current);
  }, [searchQuery]);

  // Fetch calendar data when student or month changes
  useEffect(() => {
    const fetchCalendar = async () => {
      if (!selectedStudent) return;
      
      setLoading(true);
      try {
        const res = await api.attendance.studentCalendar({
          student_id: selectedStudent.id,
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
  }, [selectedStudent, year, month]);

  const handleSelectStudent = (student) => {
    setSelectedStudent(student);
    setSearchQuery(student.name);
    setShowDropdown(false);
  };
  
  const handleMonthChange = (newYear, newMonth) => {
    setYear(newYear);
    setMonth(newMonth);
  };

  const renderCell = (dayData, day, dateStr) => {
    const isWeekend = new Date(dateStr).getDay() === 0 || new Date(dateStr).getDay() === 6;
    let statusClass = '';
    
    if (dayData) {
      if (dayData.status === 'Present') statusClass = 'status-present';
      else if (dayData.status === 'Absent') statusClass = 'status-absent';
      else if (dayData.status === 'Holiday' || dayData.status === 'Excused') statusClass = 'status-holiday';
    }

    return (
      <div key={`day-${day}`} className={`calendar-cell ${statusClass} ${isWeekend && !dayData ? 'empty' : ''}`} style={isWeekend && !dayData ? { background: 'var(--neutral-secondary)' } : {}}>
        <div className="calendar-cell-date">{day}</div>
        <div className="calendar-cell-content">
          {/* We could add an icon here if we wanted */}
        </div>
      </div>
    );
  };

  return (
    <div>
      <div className="card" style={{ marginBottom: '24px' }}>
        <label className="form-label">Search Student</label>
        <div className="student-search-container">
          <div style={{ position: 'relative' }}>
            <input 
              type="text" 
              className="form-input" 
              placeholder="Start typing a name..." 
              value={searchQuery}
              onChange={e => {
                setSearchQuery(e.target.value);
                if (selectedStudent && e.target.value !== selectedStudent.name) {
                  setSelectedStudent(null);
                }
              }}
              onFocus={() => {
                if (searchResults.length > 0) setShowDropdown(true);
              }}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
            />
            <Search size={18} style={{ position: 'absolute', right: '12px', top: '10px', color: 'var(--body-subtle)' }} />
          </div>
          
          {showDropdown && searchResults.length > 0 && (
            <div className="student-search-dropdown">
              {searchResults.map(s => (
                <div key={s.id} className="student-search-item" onClick={() => handleSelectStudent(s)}>
                  <div className="student-search-item-title">{s.name}</div>
                  <div className="student-search-item-subtitle">Grade {s.grade} - Section {s.section}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {selectedStudent ? (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '24px', borderBottom: '1px solid var(--border-default)' }}>
            <h3 style={{ fontSize: '20px', fontWeight: 600, marginBottom: '4px' }}>{selectedStudent.name}</h3>
            <p style={{ color: 'var(--body-subtle)', fontSize: '14px' }}>
              Grade {selectedStudent.grade} - Section {selectedStudent.section}
            </p>
          </div>
          
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
                    <div className="legend-color" style={{ background: 'var(--success)', opacity: 0.8 }}></div>
                    Present
                  </div>
                  <div className="legend-item">
                    <div className="legend-color" style={{ background: 'var(--danger)', opacity: 0.8 }}></div>
                    Absent
                  </div>
                  <div className="legend-item">
                    <div className="legend-color" style={{ background: 'var(--brand)', opacity: 0.8 }}></div>
                    Holiday / Excused
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '60px', color: 'var(--body-subtle)' }}>
          <Search size={48} style={{ opacity: 0.2, margin: '0 auto 16px' }} />
          <p>Search and select a student to view their attendance calendar.</p>
        </div>
      )}
    </div>
  );
}
