import React, { useState, useEffect } from 'react';
import { Search, Plus, Edit2, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
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

export default function ManageAcademics() {
  const [activeTab, setActiveTab] = useState('courses');
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState('');
  
  const [classes, setClasses] = useState([]);
  const [gradeFilter, setGradeFilter] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');
  
  const [expandedStudent, setExpandedStudent] = useState(null);
  const [assessmentsData, setAssessmentsData] = useState({});
  const [loadingAssessments, setLoadingAssessments] = useState({});
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({});
  const [editingId, setEditingId] = useState(null);

  // Modals for assessment
  const [isAssessmentModalOpen, setIsAssessmentModalOpen] = useState(false);
  const [assessmentFormData, setAssessmentFormData] = useState({});
  const [editingAssessmentId, setEditingAssessmentId] = useState(null);
  const [activeStudentId, setActiveStudentId] = useState(null);
  const [coursesList, setCoursesList] = useState([]);
  
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [confirmDeleteType, setConfirmDeleteType] = useState('item'); // 'item' or 'assessment'

  const fetchItems = async () => {
    try {
      let res;
      const params = { page, limit: 20, search };
      if (activeTab === 'courses') {
        res = await api.academics.courses.list(params);
      } else if (activeTab === 'classes') {
        res = await api.academics.classes.list(params);
      } else if (activeTab === 'teachers') {
        res = await api.academics.teachers.list(params);
      } else if (activeTab === 'students') {
        if (gradeFilter) params.grade = gradeFilter;
        if (sectionFilter) params.section = sectionFilter;
        res = await api.academics.students.list(params);
      }
      if (res) {
        setItems(res.items);
        setTotal(res.total);
        setPage(res.page);
        setPages(res.pages);
      }
    } catch (err) {
      console.error('Failed to fetch items:', err);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [activeTab, page, search, gradeFilter, sectionFilter]);

  useEffect(() => {
    if (activeTab === 'students') {
      api.academics.classes.list({ limit: 100 }).then(res => setClasses(res.items || []));
    }
  }, [activeTab]);

  useEffect(() => {
    // Fetch courses for the Subject dropdown in Add Assessment
    api.academics.courses.list({ limit: 100 }).then(res => setCoursesList(res.items || []));
  }, []);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setPage(1);
    setSearch('');
    setGradeFilter('');
    setSectionFilter('');
    setExpandedStudent(null);
    setItems([]); // Clear items to prevent rendering old data with new schema
  };

  const handleOpenModal = (item = null) => {
    if (item) {
      setFormData(item);
      setEditingId(item.id);
    } else {
      setFormData({});
      setEditingId(null);
    }
    setIsModalOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (activeTab === 'courses') {
        if (editingId) await api.academics.courses.update(editingId, formData);
        else await api.academics.courses.create(formData);
      } else if (activeTab === 'classes') {
        if (editingId) await api.academics.classes.update(editingId, formData);
        else await api.academics.classes.create(formData);
      } else if (activeTab === 'teachers') {
        if (editingId) await api.academics.teachers.update(editingId, formData);
        else await api.academics.teachers.create(formData);
      }
      setIsModalOpen(false);
      fetchItems();
    } catch (err) {
      console.error('Failed to save:', err);
    }
  };

  const handleToggleExpand = async (studentId) => {
    if (expandedStudent === studentId) {
      setExpandedStudent(null);
      return;
    }
    setExpandedStudent(studentId);
    if (!assessmentsData[studentId]) {
      setLoadingAssessments(prev => ({...prev, [studentId]: true}));
      try {
        const res = await api.academics.students.assessments(studentId);
        setAssessmentsData(prev => ({...prev, [studentId]: res}));
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingAssessments(prev => ({...prev, [studentId]: false}));
      }
    }
  };

  const handleAssessmentSubmit = async (e) => {
    e.preventDefault();
    try {
      const data = {
        subject: assessmentFormData.subject,
        type: assessmentFormData.type,
        score: parseFloat(assessmentFormData.score),
        max_score: parseFloat(assessmentFormData.max_score) || 100,
        date: assessmentFormData.date,
      };
      
      if (editingAssessmentId) {
        await api.academics.assessments.update(editingAssessmentId, data);
      } else {
        await api.academics.students.createAssessment(activeStudentId, data);
      }
      
      setIsAssessmentModalOpen(false);
      
      // Refresh assessments for that student
      const res = await api.academics.students.assessments(activeStudentId);
      setAssessmentsData(prev => ({...prev, [activeStudentId]: res}));
      
      // Refresh main list to update grade_avg
      fetchItems();
    } catch (err) {
      console.error('Failed to save assessment:', err);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      if (confirmDeleteType === 'assessment') {
        await api.academics.assessments.delete(confirmDelete.id);
        // Refresh assessments for that student
        const res = await api.academics.students.assessments(expandedStudent);
        setAssessmentsData(prev => ({...prev, [expandedStudent]: res}));
        fetchItems();
      } else {
        if (activeTab === 'courses') await api.academics.courses.delete(confirmDelete.id);
        else if (activeTab === 'classes') await api.academics.classes.delete(confirmDelete.id);
        else if (activeTab === 'teachers') await api.academics.teachers.delete(confirmDelete.id);
        fetchItems();
      }
      setConfirmDelete(null);
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>Manage Academics</h2>
          <p style={{ color: 'var(--body-subtle)' }}>Manage courses, classes, teachers, and students</p>
        </div>
        {activeTab !== 'students' && (
          <button className="btn btn-primary btn-base" onClick={() => handleOpenModal()}>
            <Plus size={18} />
            Add {activeTab.charAt(0).toUpperCase() + activeTab.slice(1, -1)}
          </button>
        )}
      </div>

      <div className="tab-bar">
        <div className={`tab-item ${activeTab === 'courses' ? 'active' : ''}`} onClick={() => handleTabChange('courses')}>Courses</div>
        <div className={`tab-item ${activeTab === 'classes' ? 'active' : ''}`} onClick={() => handleTabChange('classes')}>Classes</div>
        <div className={`tab-item ${activeTab === 'teachers' ? 'active' : ''}`} onClick={() => handleTabChange('teachers')}>Teachers</div>
        <div className={`tab-item ${activeTab === 'students' ? 'active' : ''}`} onClick={() => handleTabChange('students')}>Students</div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="search-filter-bar" style={{ padding: '24px 24px 0', display: 'flex', gap: '16px' }}>
          <div className="search-input" style={{ position: 'relative', flex: 1 }}>
            <Search size={18} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--body-subtle)' }} />
            <input 
              type="text" 
              className="form-input" 
              placeholder={`Search ${activeTab}...`} 
              style={{ paddingLeft: '40px' }}
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          {activeTab === 'students' && (
            <>
              <select className="form-input" style={{ width: '150px' }} value={gradeFilter} onChange={e => { setGradeFilter(e.target.value); setPage(1); }}>
                <option value="">All Grades</option>
                {[...new Set(classes.map(c => c.grade))].sort((a,b)=>a-b).map(g => (
                  <option key={g} value={g}>Grade {g}</option>
                ))}
              </select>
              <select className="form-input" style={{ width: '150px' }} value={sectionFilter} onChange={e => { setSectionFilter(e.target.value); setPage(1); }}>
                <option value="">All Sections</option>
                {[...new Set(classes.filter(c => !gradeFilter || c.grade == gradeFilter).map(c => c.section))].sort().map(s => (
                  <option key={s} value={s}>Section {s}</option>
                ))}
              </select>
            </>
          )}
        </div>

        <div style={{ padding: '24px', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                {activeTab === 'courses' && (
                  <>
                    <th>Code</th>
                    <th>Name</th>
                    <th>Credits</th>
                    <th>Department ID</th>
                  </>
                )}
                {activeTab === 'classes' && (
                  <>
                    <th>Name</th>
                    <th>Grade</th>
                    <th>Section</th>
                    <th>Teacher</th>
                  </>
                )}
                {activeTab === 'teachers' && (
                  <>
                    <th>Name</th>
                    <th>Subject</th>
                  </>
                )}
                {activeTab === 'students' && (
                  <>
                    <th>Name</th>
                    <th>Class</th>
                    <th>Attendance</th>
                    <th>Avg Grade</th>
                    <th>Fee Status</th>
                  </>
                )}
                <th style={{ width: '100px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <React.Fragment key={item.id}>
                <tr>
                  {activeTab === 'courses' && (
                    <>
                      <td><span className="badge badge-gray">{item.code}</span></td>
                      <td>{item.name}</td>
                      <td>{item.credits}</td>
                      <td>{item.department_id}</td>
                    </>
                  )}
                  {activeTab === 'classes' && (
                    <>
                      <td>{item.name}</td>
                      <td>{item.grade}</td>
                      <td>{item.section}</td>
                      <td>{item.teacher_name || 'Unassigned'}</td>
                    </>
                  )}
                  {activeTab === 'teachers' && (
                    <>
                      <td>{item.name}</td>
                      <td><span className="badge badge-brand">{item.subject}</span></td>
                    </>
                  )}
                  {activeTab === 'students' && (
                    <>
                      <td>{item.name}</td>
                      <td>Grade {item.grade} - {item.section}</td>
                      <td>
                        <span style={{ color: item.attendance_rate >= 0.9 ? 'var(--success)' : item.attendance_rate >= 0.75 ? 'var(--warning)' : 'var(--danger)' }}>
                          {item.attendance_rate != null ? (item.attendance_rate * 100).toFixed(1) + '%' : 'N/A'}
                        </span>
                      </td>
                      <td>{item.grade_avg != null ? item.grade_avg.toFixed(1) + '%' : 'N/A'}</td>
                      <td>
                        <span className={`badge ${item.overdue_fees > 0 ? 'badge-danger' : 'badge-success'}`}>
                          {item.overdue_fees > 0 ? `${item.overdue_fees} Overdue` : 'Paid'}
                        </span>
                      </td>
                    </>
                  )}
                  <td>
                    {activeTab === 'students' ? (
                      <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                         <button className="action-btn" onClick={() => handleToggleExpand(item.id)}>
                            {expandedStudent === item.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                         </button>
                      </div>
                    ) : (
                      <div className="row-actions" style={{ justifyContent: 'flex-end' }}>
                        <button className="action-btn" onClick={() => { setConfirmDeleteType('item'); handleOpenModal(item); }}>
                          <Edit2 size={16} />
                        </button>
                        <button className="action-btn danger" onClick={() => { setConfirmDeleteType('item'); setConfirmDelete(item); }}>
                          <Trash2 size={16} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
                {activeTab === 'students' && expandedStudent === item.id && (
                  <tr className="expanded-row" style={{ backgroundColor: 'var(--neutral-primary-soft)' }}>
                    <td colSpan="6" style={{ padding: '16px 24px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                        <h4 style={{ fontSize: '14px', color: 'var(--body-subtle)', margin: 0 }}>Assessment Breakdown</h4>
                        <button className="btn btn-secondary btn-sm" onClick={() => {
                          setAssessmentFormData({ date: new Date().toISOString().split('T')[0], max_score: 100 });
                          setEditingAssessmentId(null);
                          setActiveStudentId(item.id);
                          setIsAssessmentModalOpen(true);
                        }} style={{ padding: '4px 8px', fontSize: '12px' }}>
                          <Plus size={14} style={{ marginRight: '4px' }} />
                          Add Assessment
                        </button>
                      </div>
                      
                      {loadingAssessments[item.id] ? (
                        <div style={{ color: 'var(--body-subtle)', fontSize: '13px' }}>Loading...</div>
                      ) : assessmentsData[item.id] && assessmentsData[item.id].length > 0 ? (
                        <table style={{ background: 'var(--surface)', border: '1px solid var(--border-default)', borderRadius: '8px', overflow: 'hidden' }}>
                          <thead style={{ background: 'var(--neutral-primary-soft)' }}>
                            <tr>
                              <th style={{ padding: '8px 16px', fontSize: '12px', textAlign: 'left' }}>Date</th>
                              <th style={{ padding: '8px 16px', fontSize: '12px', textAlign: 'left' }}>Subject</th>
                              <th style={{ padding: '8px 16px', fontSize: '12px', textAlign: 'left' }}>Type</th>
                              <th style={{ padding: '8px 16px', fontSize: '12px', textAlign: 'left' }}>Score</th>
                              <th style={{ padding: '8px 16px', fontSize: '12px', textAlign: 'right', width: '80px' }}>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {assessmentsData[item.id].map((a, i) => (
                              <tr key={i}>
                                <td style={{ padding: '8px 16px', fontSize: '13px', borderBottom: '1px solid var(--border-subtle)' }}>{a.date}</td>
                                <td style={{ padding: '8px 16px', fontSize: '13px', borderBottom: '1px solid var(--border-subtle)' }}>{a.subject}</td>
                                <td style={{ padding: '8px 16px', fontSize: '13px', borderBottom: '1px solid var(--border-subtle)' }}>{a.type}</td>
                                <td style={{ padding: '8px 16px', fontSize: '13px', borderBottom: '1px solid var(--border-subtle)' }}>
                                  {a.score}/{a.max_score} ({(a.score/a.max_score*100).toFixed(0)}%)
                                </td>
                                <td style={{ padding: '8px 16px', fontSize: '13px', borderBottom: '1px solid var(--border-subtle)' }}>
                                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                                    <button className="action-btn" onClick={() => {
                                      setAssessmentFormData(a);
                                      setEditingAssessmentId(a.id);
                                      setActiveStudentId(item.id);
                                      setIsAssessmentModalOpen(true);
                                    }} style={{ padding: '4px' }}>
                                      <Edit2 size={14} />
                                    </button>
                                    <button className="action-btn danger" onClick={() => {
                                      setConfirmDeleteType('assessment');
                                      setConfirmDelete(a);
                                    }} style={{ padding: '4px' }}>
                                      <Trash2 size={14} />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div style={{ color: 'var(--body-subtle)', fontSize: '13px' }}>No assessments found.</div>
                      )}
                    </td>
                  </tr>
                )}
                </React.Fragment>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--body-subtle)' }}>
                    No {activeTab} found.
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
                <h3 className="form-modal-title">{editingId ? 'Edit' : 'Add'} {activeTab.charAt(0).toUpperCase() + activeTab.slice(1, -1)}</h3>
              </div>
              <div className="form-modal-body">
                {activeTab === 'courses' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Code</label>
                      <input type="text" className="form-input" value={formData.code || ''} onChange={e => setFormData({...formData, code: e.target.value})} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Name</label>
                      <input type="text" className="form-input" value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Credits</label>
                      <input type="number" min="1" className="form-input" value={formData.credits || 3} onChange={e => setFormData({...formData, credits: parseInt(e.target.value)})} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Department ID</label>
                      <input type="number" min="1" className="form-input" value={formData.department_id || ''} onChange={e => setFormData({...formData, department_id: parseInt(e.target.value)})} required />
                    </div>
                  </>
                )}
                {activeTab === 'classes' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Name</label>
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
                    <div className="form-group">
                      <label className="form-label">Teacher ID</label>
                      <input type="number" className="form-input" value={formData.teacher_id || ''} onChange={e => setFormData({...formData, teacher_id: parseInt(e.target.value) || null})} />
                    </div>
                  </>
                )}
                {activeTab === 'teachers' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Name</label>
                      <input type="text" className="form-input" value={formData.name || ''} onChange={e => setFormData({...formData, name: e.target.value})} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Subject</label>
                      <input type="text" className="form-input" value={formData.subject || ''} onChange={e => setFormData({...formData, subject: e.target.value})} required />
                    </div>
                  </>
                )}
              </div>
              <div className="form-modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Changes</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isAssessmentModalOpen && (
        <div className="form-modal-overlay" onClick={() => setIsAssessmentModalOpen(false)}>
          <div className="form-modal" onClick={e => e.stopPropagation()}>
            <form onSubmit={handleAssessmentSubmit}>
              <div className="form-modal-header">
                <h3 className="form-modal-title">{editingAssessmentId ? 'Edit' : 'Add'} Assessment</h3>
              </div>
              <div className="form-modal-body">
                <div className="form-group">
                  <label className="form-label">Subject</label>
                  <select 
                    className="form-input" 
                    value={assessmentFormData.subject || ''} 
                    onChange={e => setAssessmentFormData({...assessmentFormData, subject: e.target.value})} 
                    required
                  >
                    <option value="">Select Subject</option>
                    {coursesList.map(c => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Type</label>
                  <select 
                    className="form-input" 
                    value={assessmentFormData.type || ''} 
                    onChange={e => setAssessmentFormData({...assessmentFormData, type: e.target.value})} 
                    required
                  >
                    <option value="">Select Type</option>
                    <option value="Quiz">Quiz</option>
                    <option value="Midterm">Midterm</option>
                    <option value="Final">Final</option>
                    <option value="Project">Project</option>
                  </select>
                </div>
                <div className="form-group" style={{ display: 'flex', gap: '16px' }}>
                  <div style={{ flex: 1 }}>
                    <label className="form-label">Score</label>
                    <input 
                      type="number" 
                      min="0"
                      max={assessmentFormData.max_score || 100}
                      step="0.1" 
                      className="form-input" 
                      value={assessmentFormData.score || ''} 
                      onChange={e => setAssessmentFormData({...assessmentFormData, score: e.target.value})} 
                      required 
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label className="form-label">Max Score</label>
                    <input 
                      type="number" 
                      min="1"
                      step="0.1" 
                      className="form-input" 
                      value={assessmentFormData.max_score || 100} 
                      onChange={e => setAssessmentFormData({...assessmentFormData, max_score: e.target.value})} 
                      required 
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Date</label>
                  <input 
                    type="date" 
                    max={new Date().toISOString().split('T')[0]}
                    className="form-input" 
                    value={assessmentFormData.date || ''} 
                    onChange={e => setAssessmentFormData({...assessmentFormData, date: e.target.value})} 
                    required 
                  />
                </div>
              </div>
              <div className="form-modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsAssessmentModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Assessment</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmModal
          title={`Delete ${confirmDeleteType === 'assessment' ? 'Assessment' : activeTab.charAt(0).toUpperCase() + activeTab.slice(1, -1)}`}
          message={`Are you sure you want to delete this ${confirmDeleteType === 'assessment' ? 'assessment' : activeTab.slice(0, -1)}? This action cannot be undone.`}
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(null)}
          confirmLabel="Delete"
        />
      )}
    </div>
  );
}
