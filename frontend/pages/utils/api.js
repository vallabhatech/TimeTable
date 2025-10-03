import axios from 'axios';

// Environment-aware API base URL
const getApiBaseUrl = () => {
  // Check if we're in production (Vercel)
  if (process.env.NODE_ENV === 'production') {
    // Use environment variable for production API URL
    return process.env.NEXT_PUBLIC_API_URL || 'https://timetable-generation-tc7o.onrender.com';
  }
  // Use localhost for development
  return 'http://localhost:8000';
};

const api = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add JWT token to all requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
}, error => {
  return Promise.reject(error);
});

// Handle token refresh on 401 errors
api.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(`${getApiBaseUrl()}/api/auth/refresh/`, {
            refresh: refreshToken
          });

          localStorage.setItem('access_token', response.data.access);
          originalRequest.headers.Authorization = `Bearer ${response.data.access}`;

          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed, clear tokens and redirect to login
          try {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user');
          } catch (_) {}
          window.location.href = '/components/Login';
          return Promise.reject(refreshError);
        }
      } else {
        // No refresh token, clear tokens and redirect to login
        try {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
        } catch (_) {}
        window.location.href = '/components/Login';
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

export default api;