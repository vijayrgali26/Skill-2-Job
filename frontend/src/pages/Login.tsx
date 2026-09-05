import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/Toast';
import { AxiosError } from 'axios';

export default function Login() {
  const { login, isAuthenticated, isLoading, user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Redirect already-authenticated users — inside useEffect, never in render
  useEffect(() => {
    if (!isLoading && isAuthenticated && user) {
      const target =
        user.role === 'placement_officer' || user.role === 'admin'
          ? '/admin/dashboard'
          : '/student/dashboard';
      navigate(target, { replace: true });
    }
  }, [isLoading, isAuthenticated, user, navigate]);

  // Show nothing while checking session (avoids flash of login form)
  if (isLoading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: '#f8fafc', color: '#64748b',
      }}>
        Loading...
      </div>
    );
  }

  const successMessage =
    (location.state as { message?: string } | null)?.message ?? '';
  const requestedRole = new URLSearchParams(location.search).get('role');
  const roleLabel =
    requestedRole === 'admin'
      ? 'admin'
      : requestedRole === 'placement_officer'
        ? 'placement officer'
        : 'student';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !password.trim()) {
      setError('Please enter both email and password.');
      return;
    }

    setLoading(true);
    try {
      const authUser = await login(email, password);
      showToast(`Welcome back, ${authUser.name}!`, 'success');

      const target =
        authUser.role === 'placement_officer' || authUser.role === 'admin'
          ? '/admin/dashboard'
          : '/student/dashboard';
      navigate(target, { replace: true });
    } catch (err) {
      if (err instanceof AxiosError && err.response) {
        setError('Invalid email or password.');
        showToast('Invalid credentials', 'error');
      } else {
        setError('Unable to connect to the server. Please try again later.');
        showToast('Connection error', 'error');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-brand">Skill2Job</h1>
        <h2 className="auth-subtitle">Sign in as {roleLabel}</h2>

        {successMessage && (
          <div className="auth-success-banner">{successMessage}</div>
        )}

        {error && <div className="auth-error-banner">{error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label htmlFor="email" className="auth-label">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="auth-input"
              placeholder="you@example.com"
              autoComplete="email"
              disabled={loading}
            />
          </div>

          <div className="auth-field">
            <label htmlFor="password" className="auth-label">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="auth-input"
              placeholder="Enter your password"
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          <button type="submit" disabled={loading} className="auth-button">
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="auth-links">
          <p className="auth-footer">
            Don&apos;t have an account?{' '}
            <Link to="/register">Register</Link>
          </p>
          <p className="auth-footer">
            Forgot your password?{' '}
            <Link to="/forgot-password">Reset Password</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
