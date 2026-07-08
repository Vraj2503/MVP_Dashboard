import React, { useState, useEffect } from 'react';
import { Search, Plus, Edit2, Trash2, ChevronDown, ChevronRight, Activity } from 'lucide-react';
import { api } from '../api/client';
import ConfirmModal from '../components/ConfirmModal';

function Pagination({ page, pages, onPageChange }) {
  return (
    <div className="pagination-bar">
      <div className="pagination-info">
        Page {page} of {pages}
      </div>
      <div className="pagination-controls">
        <button 
          className="page-btn" 
          disabled={page <= 1} 
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        <button 
          className="page-btn" 
          disabled={page >= pages} 
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

function StudentDetailPanel({ studentId }) {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const res = await api.students.details(studentId);
        setDetails(res);
      } catch (err) {
        console.error('Failed to load student details:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [studentId]);

  if (loading) return <div style={{ padding: '24px', textAlign: 'center', color: 'var(--body-subtle)' }}>Loading details...</div>;
  if (!details) return <div style={{ padding: '24px', textAlign: 'center', color: 'var(--body-subtle)' }}>Failed to load details.</div>;

  return (
    <div className="expandable-detail">
      <h4 style={{ marginBottom: '16px', fontSize: '15px' }}>Academic Performance Breakdown</h4>
      {details.grades && details.grades.length > 0 ? (
        <div className="detail-grid">
          {details.grades.map(g => (
            <div key={g.subject} className="detail-item">
              <div style={{ color: 'var(--body-subtle)', fontSize: '12px', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{g.subject}</div>
              <div style={{ fontSize: '24px', fontWeight: '600', color: 'var(--heading)' }}>
                {g.average_score.toFixed(1)}%
              </div>
              <div style={{ fontSize: '12px', color: 'var(--body-subtle)', marginTop: '4px' }}>
                {g.assessment_count} assessments
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: 'var(--body-subtle)', fontSize: '14px' }}>No academic assessments recorded yet.</p>
      )}
    </div>
  );
}

export default function ManageStudents() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  
  const [search, setSearch] = useState('');
  const [gradeFilter, setGradeFilter] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');
  
  const [expandedRow, setExpandedRow] = useState(null);
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
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

  const fetchItems = async () => {
    try {
      const params = { page, limit: 20, search };
      if (gradeFilter) params.grade = gradeFilter;
      if (sectionFilter) params.section = sectionFilter;
      
      const res = await api.students.list(params);
      setItems(res.items);
      setTotal(res.total);
      setPage(res.page);
      setPages(res.pages);
    } catch (err) {
      console.error('Failed to fetch students:', err);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [page, search, gradeFilter, sectionFilter]);

  const toggleRow = (id) => {
    if (expandedRow === id) setExpandedRow(null);
    else setExpandedRow(id);
  };

  const handleOpenModal = (item = null) => {
    if (item) {
      setFormData(item);
      setEditingId(item.id);
    } else {
      setFormData({
        gender: 'M', // default value
        enrollment_date: new Date().toISOString().split('T')[0]
      });
      setEditingId(null);
    }
    setIsModalOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingId) await api.students.update(editingId, formData);
      else await api.students.create(formData);
      
      setIsModalOpen(false);
      fetchItems();
    } catch (err) {
      console.error('Failed to save student:', err);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await api.students.delete(confirmDelete.id);
      setConfirmDelete(null);
      fetchItems();
    } catch (err) {
      console.error('Failed to delete student:', err);
    }
  };

  const renderColorBadge = (value, type) => {
    if (value === null || value === undefined) return <span style={{ color: 'var(--body-subtle)' }}>N/A</span>;
    
    let colorClass = 'badge-neutral';
    if (type === 'attendance') {
      const val = value * 100;
      if (val >= 90) colorClass = 'badge-success';
      else if (val >= 75) colorClass = 'badge-warning';
      else colorClass = 'badge-danger';
      return <span className={`badge ${colorClass}`}>{val.toFixed(1)}%</span>;
    } else if (type === 'grade') {
      if (value >= 85) colorClass = 'badge-success';
      else if (value >= 70) colorClass = 'badge-warning';
      else colorClass = 'badge-danger';
      return <span className={`badge ${colorClass}`}>{value.toFixed(1)}%</span>;
    }
  };

  const availableGrades = [...new Set(availableClasses.map(c => c.grade))].sort((a, b) => a - b);
  const availableSections = gradeFilter
    ? [...new Set(availableClasses.filter(c => c.grade === parseInt(gradeFilter)).map(c => c.section))].sort()
    : [...new Set(availableClasses.map(c => c.section))].sort();

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>Manage Students</h2>
          <p style={{ color: 'var(--body-subtle)' }}>View, add, edit, and analyze student records</p>
        </div>
        <button className="btn btn-primary btn-base" onClick={() => handleOpenModal()}>
          <Plus size={18} />
          Add Student
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="search-filter-bar" style={{ padding: '24px 24px 0' }}>
          <div className="search-input" style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--body-subtle)' }} />
            <input 
              type="text" 
              className="form-input" 
              placeholder="Search by name..." 
              style={{ paddingLeft: '40px' }}
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          <div>
            <select className="form-select" value={gradeFilter} onChange={e => { setGradeFilter(e.target.value); setPage(1); }}>
              <option value="">All Grades</option>
              {availableGrades.map(g => (
                <option key={g} value={g}>Grade {g}</option>
              ))}
            </select>
          </div>
          <div>
            <select className="form-select" value={sectionFilter} onChange={e => { setSectionFilter(e.target.value); setPage(1); }}>
              <option value="">All Sections</option>
              {availableSections.map(s => (
                <option key={s} value={s}>Section {s}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ padding: '24px', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: '40px' }}></th>
                <th>Name</th>
                <th>Grade</th>
                <th>Section</th>
                <th>Gender</th>
                <th>Attendance</th>
                <th>Avg Grade</th>
                <th style={{ width: '100px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <React.Fragment key={item.id}>
                  <tr className="row-expandable" onClick={() => toggleRow(item.id)}>
                    <td style={{ color: 'var(--body-subtle)' }}>
                      {expandedRow === item.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    </td>
                    <td style={{ fontWeight: '500' }}>{item.name}</td>
                    <td>{item.grade}</td>
                    <td>{item.section}</td>
                    <td>{item.gender}</td>
                    <td>{renderColorBadge(item.attendance_rate, 'attendance')}</td>
                    <td>{renderColorBadge(item.grade_avg, 'grade')}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                        <button className="action-btn" onClick={() => handleOpenModal(item)}>
                          <Edit2 size={16} />
                        </button>
                        <button className="action-btn danger" onClick={() => setConfirmDelete(item)}>
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedRow === item.id && (
                    <tr>
                      <td colSpan={8} style={{ padding: 0, borderBottom: '1px solid var(--border-default)' }}>
                        <StudentDetailPanel studentId={item.id} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--body-subtle)' }}>
                    No students found matching your criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        
        {pages > 1 && <Pagination page={page} pages={pages} onPageChange={setPage} />}
      </div>

      {isModalOpen && (
        <div className="form-modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="form-modal" onClick={e => e.stopPropagation()}>
            <form onSubmit={handleSubmit}>
              <div className="form-modal-header">
                <h3 className="form-modal-title">{editingId ? 'Edit Student' : 'Add New Student'}</h3>
              </div>
              <div className="form-modal-body">
                <div className="form-group">
                  <label className="form-label">Full Name</label>
                  <input type="text" className="form-input" value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} required />
                </div>
                
                <div className="form-group" style={{ display: 'flex', gap: '16px' }}>
                  <div style={{ flex: 1 }}>
                    <label className="form-label">Grade</label>
                    <input type="number" min="9" max="12" className="form-input" value={formData.grade || ''} onChange={e => setFormData({...formData, grade: parseInt(e.target.value)})} required />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label className="form-label">Section</label>
                    <input type="text" pattern="[A-Ea-e]" maxLength="1" title="Section A to E" className="form-input" value={formData.section || ''} onChange={e => setFormData({...formData, section: e.target.value})} required />
                  </div>
                </div>

                <div className="form-group" style={{ display: 'flex', gap: '16px' }}>
                  <div style={{ flex: 1 }}>
                    <label className="form-label">Gender</label>
                    <select className="form-select" value={formData.gender || 'M'} onChange={e => setFormData({...formData, gender: e.target.value})} required>
                      <option value="M">Male</option>
                      <option value="F">Female</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                  <div style={{ flex: 1 }}>
                    <label className="form-label">Date of Birth</label>
                    <input type="date" max={new Date().toISOString().split('T')[0]} className="form-input" value={formData.dob || ''} onChange={e => setFormData({...formData, dob: e.target.value})} required />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Enrollment Date</label>
                  <input type="date" max={new Date().toISOString().split('T')[0]} className="form-input" value={formData.enrollment_date || ''} onChange={e => setFormData({...formData, enrollment_date: e.target.value})} required />
                </div>

                <div className="form-group">
                  <label className="form-label">Parent Contact</label>
                  <input type="text" pattern="^[0-9+\\- ()]+$" title="Valid phone number characters only" className="form-input" value={formData.parent_contact || ''} onChange={e => setFormData({...formData, parent_contact: e.target.value})} required />
                </div>
              </div>
              <div className="form-modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Changes</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmModal
          title="Delete Student"
          message={`Are you sure you want to delete ${confirmDelete.name}? This will permanently remove the student and all related records.`}
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(null)}
          confirmLabel="Delete"
        />
      )}
    </div>
  );
}
