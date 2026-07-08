// Centralized API Client

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function fetchAPI(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const finalOptions = { ...defaultOptions, ...options };
  
  try {
    const response = await fetch(url, finalOptions);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

export const api = {
  dashboard: {
    getStatic: () => fetchAPI('/dashboard/static'),
    getAdaptive: (startDate, endDate) => {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      const qs = params.toString();
      return fetchAPI(`/dashboard/adaptive${qs ? `?${qs}` : ''}`);
    },
  },
  chat: {
    send: (question, sessionId = null, userId = 'admin') => 
      fetchAPI('/chat', { method: 'POST', body: JSON.stringify({ question, user_id: userId, session_id: sessionId }) }),
    feedback: (logId, feedback) => 
      fetchAPI('/chat/feedback', { method: 'POST', body: JSON.stringify({ log_id: logId, feedback }) }),
  },
  digests: {
    list: () => fetchAPI('/digests'),
    generate: (startDate, endDate) => {
      let url = '/digests/generate';
      if (startDate && endDate) {
         url += `?start_date=${startDate}&end_date=${endDate}`;
      }
      return fetchAPI(url, { method: 'POST' });
    },
    delete: (id) => fetchAPI(`/digests/${id}`, { method: 'DELETE' }),
    clearAll: () => fetchAPI('/digests', { method: 'DELETE' }),
  },
  observability: {
    getSummary: () => fetchAPI('/observability/summary'),
    getFailed: () => fetchAPI('/observability/failed'),
    getGolden: () => fetchAPI('/observability/golden'),
    runGolden: () => fetchAPI('/observability/golden/run', { method: 'POST' }),
    clearFailed: () => fetchAPI('/observability/failed', { method: 'DELETE' }),
    clearAll: () => fetchAPI('/observability/logs', { method: 'DELETE' }),
  },
  alerts: {
    list: (filters = {}) => {
      const params = new URLSearchParams();
      if (filters.severity) params.append('severity', filters.severity);
      if (filters.status) params.append('status', filters.status);
      if (filters.type) params.append('type', filters.type);
      if (filters.limit) params.append('limit', filters.limit);
      if (filters.offset) params.append('offset', filters.offset);
      const qs = params.toString();
      return fetchAPI(`/alerts${qs ? `?${qs}` : ''}`);
    },
    unreadCount: () => fetchAPI('/alerts/unread-count'),
    updateStatus: (id, status) =>
      fetchAPI(`/alerts/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
    scan: () => fetchAPI('/alerts/scan', { method: 'POST' }),
  },
  academics: {
    courses: {
      list: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return fetchAPI(`/academics/courses${qs ? `?${qs}` : ''}`);
      },
      create: (data) => fetchAPI('/academics/courses', { method: 'POST', body: JSON.stringify(data) }),
      update: (id, data) => fetchAPI(`/academics/courses/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
      delete: (id) => fetchAPI(`/academics/courses/${id}`, { method: 'DELETE' }),
    },
    classes: {
      list: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return fetchAPI(`/academics/classes${qs ? `?${qs}` : ''}`);
      },
      create: (data) => fetchAPI('/academics/classes', { method: 'POST', body: JSON.stringify(data) }),
      update: (id, data) => fetchAPI(`/academics/classes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
      delete: (id) => fetchAPI(`/academics/classes/${id}`, { method: 'DELETE' }),
    },
    teachers: {
      list: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return fetchAPI(`/academics/teachers${qs ? `?${qs}` : ''}`);
      },
      create: (data) => fetchAPI('/academics/teachers', { method: 'POST', body: JSON.stringify(data) }),
      update: (id, data) => fetchAPI(`/academics/teachers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
      delete: (id) => fetchAPI(`/academics/teachers/${id}`, { method: 'DELETE' }),
    },
    students: {
      list: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return fetchAPI(`/academics/students${qs ? `?${qs}` : ''}`);
      },
      assessments: (studentId) => fetchAPI(`/academics/students/${studentId}/assessments`),
      createAssessment: (studentId, data) => fetchAPI(`/academics/students/${studentId}/assessments`, { method: 'POST', body: JSON.stringify(data) }),
    },
    assessments: {
      update: (id, data) => fetchAPI(`/academics/assessments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
      delete: (id) => fetchAPI(`/academics/assessments/${id}`, { method: 'DELETE' }),
    },
  },
  students: {
    list: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return fetchAPI(`/students${qs ? `?${qs}` : ''}`);
    },
    details: (id) => fetchAPI(`/students/${id}/details`),
    create: (data) => fetchAPI('/students', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => fetchAPI(`/students/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id) => fetchAPI(`/students/${id}`, { method: 'DELETE' }),
  },
  attendance: {
    classView: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return fetchAPI(`/attendance/class${qs ? `?${qs}` : ''}`);
    },
    bulkSave: (data) => fetchAPI('/attendance/bulk', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => fetchAPI(`/attendance/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id) => fetchAPI(`/attendance/${id}`, { method: 'DELETE' }),
  },
};
