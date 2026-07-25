import axios from 'axios';

// Base URL points to the local FastAPI backend
const API_BASE_URL = 'http://127.0.0.1:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intercept requests to add the auth token if it exists
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('northstar_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth Endpoints
export const registerUser = async (fullName, email, password) => {
  try {
    const response = await apiClient.post('/auth/register', { full_name: fullName, email, password });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Registration failed');
  }
};

export const loginUser = async (email, password) => {
  try {
    const response = await apiClient.post('/auth/login', { email, password });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || 'Login failed');
  }
};

export const getMe = async () => {
  try {
    const response = await apiClient.get('/auth/me');
    return response.data;
  } catch (error) {
    throw new Error('Not authenticated');
  }
};

export const askQuestion = async (question) => {
  try {
    const response = await apiClient.post('/ask', {
      question: question.trim(),
      top_k: 4,
      minimum_relevance: 0.55,
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || `Server Error: ${error.response.status}`);
    } else if (error.request) {
      throw new Error('Failed to connect to the server. Is the backend running?');
    } else {
      throw new Error(error.message);
    }
  }
};
