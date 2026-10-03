import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../lib/api.js';
import { setToken, setupAutoLogout } from '../lib/session.js';
import { Toast } from '../components/Toast.jsx';
import { Spinner } from '../components/Spinner.jsx';

export function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');

    if (!email || !password) {
      setErrorMsg('Email and password are required.');
      return;
    }

    setLoading(true);
    try {
      const data = await api.post('/auth/login', { email, password });
      if (data && data.access_token) {
        setToken(data.access_token);
        if (onLoginSuccess) {
          onLoginSuccess(data.access_token);
        }
        navigate('/dashboard');
      } else {
        setErrorMsg('Invalid response from server.');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100vw',
        height: '100vh',
        backgroundColor: 'var(--bg-primary)',
      }}
    >
      <div className="card" style={{ width: '380px' }}>
        <h2 className="card-title" style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          EMS Login
        </h2>
        <Toast type="error" message={errorMsg} />
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="email">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@ems.com"
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={loading}
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
            {loading ? <Spinner /> : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
