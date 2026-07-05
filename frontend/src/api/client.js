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
};
