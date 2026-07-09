import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function AttendanceCalendar({ year, month, data, renderCell, onMonthChange }) {
  const date = new Date(year, month - 1, 1);
  const monthName = date.toLocaleString('default', { month: 'long' });
  
  // Calculate days
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDayOfWeek = date.getDay(); // 0 is Sunday, 1 is Monday...
  
  // Adjust to make Monday the first day of the week (0 = Mon, 6 = Sun)
  const emptyDays = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;
  
  const handlePrevMonth = () => {
    if (month === 1) onMonthChange(year - 1, 12);
    else onMonthChange(year, month - 1);
  };
  
  const handleNextMonth = () => {
    if (month === 12) onMonthChange(year + 1, 1);
    else onMonthChange(year, month + 1);
  };
  
  // Create a map of data by date string (YYYY-MM-DD) for easy lookup
  const dataMap = {};
  if (data && Array.isArray(data)) {
    data.forEach(item => {
      dataMap[item.date] = item;
    });
  }

  return (
    <div className="calendar-container">
      <div className="calendar-header">
        <h3>{monthName} {year}</h3>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary btn-sm" onClick={handlePrevMonth}>
            <ChevronLeft size={16} />
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleNextMonth}>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
      
      <div className="calendar-grid-header">
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => (
          <div key={day} className="calendar-day-name">{day}</div>
        ))}
      </div>
      
      <div className="calendar-grid">
        {/* Empty cells before the 1st of the month */}
        {Array.from({ length: emptyDays }).map((_, i) => (
          <div key={`empty-${i}`} className="calendar-cell empty"></div>
        ))}
        
        {/* Days of the month */}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const day = i + 1;
          const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const dayData = dataMap[dateStr];
          
          return renderCell(dayData, day, dateStr);
        })}
      </div>
    </div>
  );
}
