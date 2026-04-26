/**
 * Login.js
 * ────────
 * JWT login + self-registration form.
 * On success it calls onLogin(user) so App.js can switch to the main layout.
 */

import React, { useState } from 'react';
import axios from 'axios';
import { login } from '../auth';

const ROLES = ['coach', 'scout', 'physio', 'nutritionist'];

const FIELD_LABELS = {
  username: 'Username',
  password: 'Password',
  email: 'Email',
  first_name: 'First name',
  last_name: 'Last name',
  role: 'Role',
  non_field_errors: 'Form',
  detail: 'Error',
};

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
}

function formatApiError(err, mode) {
  const status = err?.response?.status;
  const data = err?.response?.data;

  if (status === 401) {
    return 'Invalid username or password. Check your credentials and try again.';
  }

  if (status === 400 && data && typeof data === 'object') {
    const lines = [];
    for (const [field, rawValue] of Object.entries(data)) {
      const values = Array.isArray(rawValue) ? rawValue : [rawValue];
      for (const value of values) {
        const label = FIELD_LABELS[field] || field;
        lines.push(`${label}: ${value}`);
      }
    }
    if (lines.length) return lines.join('\n');
  }

  if (typeof data === 'string' && data.trim()) {
    return data;
  }

  if (typeof data === 'object' && data?.detail) {
    return data.detail;
  }

  if (mode === 'register') {
    return 'Registration failed. Please verify your form values and try again.';
  }
  return 'Sign in failed. Please check your credentials and try again.';
}

export default function Login({ onLogin }) {
  const [mode,    setMode]    = useState('login'); // 'login' | 'register'
  const [form,    setForm]    = useState({ username: '', password: '', email: '', first_name: '', last_name: '', role: 'coach' });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const [success, setSuccess] = useState('');

  const handleChange = (e) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
    setError('');
    setSuccess('');
  };

  const switchMode = (m) => {
    setMode(m);
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.username || !form.password) {
      setError('Username and password are required.');
      return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (mode === 'register' && !form.email) {
      setError('Email is required.');
      return;
    }
    if (mode === 'register' && !isValidEmail(form.email)) {
      setError('Please enter a valid email address (example: name@club.com).');
      return;
    }
    setLoading(true);
    try {
      if (mode === 'login') {
        const user = await login(form.username, form.password);
        onLogin(user);
      } else {
        // Register then auto-login
        await axios.post('/api/auth/register/', {
          username:   form.username,
          password:   form.password,
          email:      form.email,
          first_name: form.first_name,
          last_name:  form.last_name,
          role:       form.role,
        });
        setSuccess('Account created! Signing you in…');
        const user = await login(form.username, form.password);
        onLogin(user);
      }
    } catch (err) {
      setError(formatApiError(err, mode));
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    width: '100%', boxSizing: 'border-box',
    padding: '11px 14px', marginBottom: 14,
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid var(--border-color)',
    borderRadius: 8, color: 'var(--text-primary)',
    fontSize: 14, outline: 'none',
    transition: 'border-color 0.2s',
  };
  const labelStyle = {
    display: 'block', marginBottom: 6,
    fontSize: 12, fontWeight: 700,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase', letterSpacing: '0.06em',
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-primary)',
    }}>
      <div style={{
        width: '100%', maxWidth: 440,
        background: 'var(--bg-card)',
        border: '1px solid var(--border-color)',
        borderRadius: 16, padding: '40px 36px 36px',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 14,
            background: 'linear-gradient(135deg, var(--neon-cyan) 0%, var(--neon-pink) 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, margin: '0 auto 12px',
          }}>⚽</div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: 'var(--text-primary)' }}>SmartClub</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>Club Intelligence Platform</p>
        </div>

        {/* Tab switch */}
        <div style={{
          display: 'flex', borderRadius: 8, overflow: 'hidden',
          border: '1px solid var(--border-color)', marginBottom: 24,
        }}>
          {['login', 'register'].map((m) => (
            <button key={m} onClick={() => switchMode(m)} style={{
              flex: 1, padding: '9px 0', fontWeight: 700, fontSize: 13,
              cursor: 'pointer', border: 'none', letterSpacing: '0.04em',
              textTransform: 'capitalize', transition: 'all 0.18s',
              background: mode === m ? 'var(--neon-cyan)' : 'transparent',
              color:      mode === m ? '#0d0f15'          : 'var(--text-muted)',
            }}>
              {m === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} autoComplete="on">

          {/* Register-only fields */}
          {mode === 'register' && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={labelStyle}>First Name</label>
                  <input name="first_name" type="text" value={form.first_name}
                    onChange={handleChange} placeholder="First" style={inputStyle}
                    onFocus={e => e.target.style.borderColor = 'var(--neon-cyan)'}
                    onBlur={e  => e.target.style.borderColor = 'var(--border-color)'} />
                </div>
                <div>
                  <label style={labelStyle}>Last Name</label>
                  <input name="last_name" type="text" value={form.last_name}
                    onChange={handleChange} placeholder="Last" style={inputStyle}
                    onFocus={e => e.target.style.borderColor = 'var(--neon-cyan)'}
                    onBlur={e  => e.target.style.borderColor = 'var(--border-color)'} />
                </div>
              </div>
              <label style={labelStyle}>Email</label>
              <input name="email" type="email" value={form.email}
                onChange={handleChange} placeholder="you@club.com"
                style={inputStyle} autoComplete="email"
                onFocus={e => e.target.style.borderColor = 'var(--neon-cyan)'}
                onBlur={e  => e.target.style.borderColor = 'var(--border-color)'} />
              <label style={labelStyle}>Role</label>
              <select name="role" value={form.role} onChange={handleChange} style={{
                ...inputStyle,
                appearance: 'none', cursor: 'pointer',
              }}>
                {ROLES.map(r => (
                  <option key={r} value={r} style={{ background: '#1a1d27' }}>
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </option>
                ))}
              </select>
            </>
          )}

          {/* Shared fields */}
          <label style={labelStyle}>Username</label>
          <input name="username" type="text" value={form.username}
            onChange={handleChange} placeholder="Enter username"
            style={inputStyle} autoComplete="username"
            onFocus={e => e.target.style.borderColor = 'var(--neon-cyan)'}
            onBlur={e  => e.target.style.borderColor = 'var(--border-color)'} />

          <label style={labelStyle}>Password</label>
          <input name="password" type="password" value={form.password}
            onChange={handleChange} placeholder={mode === 'register' ? 'Min 8 characters' : 'Enter password'}
            style={{ ...inputStyle, marginBottom: 8 }} autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            onFocus={e => e.target.style.borderColor = 'var(--neon-cyan)'}
            onBlur={e  => e.target.style.borderColor = 'var(--border-color)'} />

          {/* Feedback */}
          {error && (
            <div style={{
              padding: '9px 12px', marginBottom: 12, borderRadius: 7,
              background: 'rgba(242,73,92,0.12)', border: '1px solid rgba(242,73,92,0.3)',
              color: '#f2495c', fontSize: 12, fontWeight: 500, whiteSpace: 'pre-line',
            }}>⚠ {error}</div>
          )}
          {success && (
            <div style={{
              padding: '9px 12px', marginBottom: 12, borderRadius: 7,
              background: 'rgba(55,217,192,0.12)', border: '1px solid rgba(55,217,192,0.3)',
              color: 'var(--neon-cyan)', fontSize: 12, fontWeight: 500,
            }}>✓ {success}</div>
          )}

          <button type="submit" disabled={loading} style={{
            width: '100%', padding: '12px', marginTop: 4,
            background: loading
              ? 'rgba(55,217,192,0.3)'
              : 'linear-gradient(135deg, var(--neon-cyan) 0%, rgba(55,217,192,0.7) 100%)',
            border: 'none', borderRadius: 8,
            color: loading ? 'rgba(255,255,255,0.5)' : '#0d0f15',
            fontWeight: 800, fontSize: 14, cursor: loading ? 'not-allowed' : 'pointer',
            letterSpacing: '0.04em', transition: 'all 0.2s',
          }}>
            {loading ? (mode === 'login' ? 'Signing in…' : 'Creating account…') : (mode === 'login' ? 'Sign In' : 'Create Account')}
          </button>
        </form>

        <div style={{ marginTop: 20, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
          SmartClub Analytics v1.0 · Secure JWT Auth
        </div>
      </div>
    </div>
  );
}
