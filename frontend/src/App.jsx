import React, { useState, useEffect } from 'react';
import Chatbot from './components/Chatbot';
import AuthScreen from './components/ui/AuthScreen';
import { getMe } from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('northstar_token');
      if (token) {
        try {
          const userData = await getMe();
          setUser(userData);
          setIsAuthenticated(true);
        } catch (error) {
          // Token invalid or expired
          localStorage.removeItem('northstar_token');
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const handleLoginSuccess = async (token) => {
    localStorage.setItem('northstar_token', token);
    try {
      const userData = await getMe();
      setUser(userData);
      setIsAuthenticated(true);
    } catch (error) {
      console.error("Failed to fetch user data after login", error);
      localStorage.removeItem('northstar_token');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('northstar_token');
    setIsAuthenticated(false);
    setUser(null);
  };

  if (loading) {
    // Basic loading state while checking token
    return (
      <div style={{ minHeight: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#03040a', color: '#818cf8' }}>
        <p>Initializing...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen onLoginSuccess={handleLoginSuccess} />;
  }

  return <Chatbot user={user} onLogout={handleLogout} />;
}

export default App;
