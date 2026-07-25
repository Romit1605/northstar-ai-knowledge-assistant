import React, { useState } from 'react';
import { loginUser, registerUser } from '../../services/api';
import SpaceBackground from './SpaceBackground';
import './AuthScreen.css';

export default function AuthScreen({ onLoginSuccess }) {
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Form fields
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        const response = await loginUser(email, password);
        onLoginSuccess(response.access_token);
      } else {
        // Register flow
        await registerUser(fullName, email, password);
        // Auto-login after register
        const loginRes = await loginUser(email, password);
        onLoginSuccess(loginRes.access_token);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    setError('');
  };

  return (
    <>
      <SpaceBackground />
      
      <div className="auth-container">
        <div className="auth-card glass-panel">
          <div className="auth-header">
            <div className="auth-icon">✦</div>
            <h1>Northstar AI</h1>
            <p>{isLogin ? 'Sign in to continue' : 'Create your account'}</p>
          </div>

          {error && <div className="auth-error" role="alert">{error}</div>}

          <form className="auth-form" onSubmit={handleSubmit}>
            {!isLogin && (
              <div className="form-group">
                <label htmlFor="fullName">Full Name</label>
                <input 
                  id="fullName" 
                  type="text" 
                  className="auth-input"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                  required={!isLogin}
                  disabled={loading}
                  minLength={2}
                />
              </div>
            )}

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input 
                id="email" 
                type="email" 
                className="auth-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                required
                disabled={loading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <div className="password-input-wrapper">
                <input 
                  id="password" 
                  type={showPassword ? "text" : "password"}
                  className="auth-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  disabled={loading}
                  minLength={isLogin ? 1 : 8}
                />
                <button 
                  type="button"
                  className="btn-show-password"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              {!isLogin && <small className="password-hint">Must be at least 8 characters</small>}
            </div>

            <button 
              type="submit" 
              className="btn btn-auth" 
              disabled={loading || !email || !password || (!isLogin && !fullName)}
            >
              {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Create Account')}
            </button>
          </form>

          <div className="auth-footer">
            <p>
              {isLogin ? "Don't have an account?" : "Already have an account?"}
              <button className="btn-link" onClick={toggleMode} disabled={loading}>
                {isLogin ? "Create one" : "Sign in"}
              </button>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
