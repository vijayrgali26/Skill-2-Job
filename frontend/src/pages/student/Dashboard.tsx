import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import { useToast } from '../../components/Toast';

interface JobRecommendation {
  job_role_id: number;
  title: string;
  company_name: string;
  compatibility_score: number;
}

interface PredictionData {
  probability: number;
  confidence?: string;
  factors?: Array<{ factor: string; impact: string }>;
}

interface StudentDashboardData {
  profile_completeness: number;
  skill_count: number;
  skill_breakdown: Record<string, number>;
  matched_job_count: number;
  top_recommendations: JobRecommendation[];
  dream_job_progress: {
    dream_job: string | null;
    target_job: { id: number; title: string } | null;
    match_score: number;
    matched_skills: number;
    required_skills: number;
    missing_skills: string[];
    recommended_courses: Array<{
      skill: string;
      courses: Array<{
        id: number;
        course_name: string;
        provider: string | null;
        url: string | null;
      }>;
    }>;
  };
}

export default function StudentDashboard() {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [data, setData] = useState<StudentDashboardData | null>(null);
  const [prediction, setPrediction] = useState<PredictionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const [dashRes, predRes] = await Promise.allSettled([
        api.get('/dashboard/student'),
        api.get('/dashboard/student/prediction'),
      ]);

      if (dashRes.status === 'fulfilled') {
        setData(dashRes.value.data);
      }

      if (predRes.status === 'fulfilled') {
        const pred = predRes.value.data;
        // Only set prediction if it has valid data (no error key)
        if (pred && typeof pred.probability === 'number' && !pred.error) {
          setPrediction(pred);
        } else {
          // Provide safe defaults so the ring still renders
          setPrediction({ probability: 0, confidence: 'low', factors: [] });
        }
      }
    } catch {
      showToast('Failed to load dashboard', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const handleLogout = () => {
    logout();
    showToast('Logged out successfully', 'info');
    navigate('/');
  };

  const readinessScore = prediction?.probability ?? 0;
  const profileComplete = data?.profile_completeness ?? 0;
  const factors = prediction?.factors ?? [];

  if (loading) {
    return (
      <div className="student-layout">
        <StudentSidebar
          active="dashboard"
          sidebarOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          onLogout={handleLogout}
        />
        <main className="student-main">
          <div className="dash-loading">Loading dashboard...</div>
        </main>
      </div>
    );
  }

  const ringColor =
    readinessScore >= 70 ? '#10b981' : readinessScore >= 40 ? '#f59e0b' : '#ef4444';

  return (
    <div className="student-layout">
      <StudentSidebar
        active="dashboard"
        sidebarOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onLogout={handleLogout}
      />

      <main className="student-main">
        {/* Mobile header */}
        <button className="mobile-menu-btn" onClick={() => setSidebarOpen(true)}>
          ☰
        </button>

        {/* Welcome */}
        <div className="welcome-section">
          <h1 className="welcome-title">Welcome back, {user?.name ?? 'Student'}! 👋</h1>
          <p className="welcome-sub">Here's your placement journey overview</p>
        </div>

        {/* Stats Grid */}
        <div className="stats-grid-student">
          <div className="stat-widget stat-widget-primary" style={{ opacity: 1 }}>
            <div className="stat-widget-icon">🎯</div>
            <div className="stat-widget-value">{readinessScore.toFixed(0)}%</div>
            <div className="stat-widget-label">Placement Readiness</div>
          </div>
          <div className="stat-widget stat-widget-success" style={{ opacity: 1 }}>
            <div className="stat-widget-icon">📊</div>
            <div className="stat-widget-value">{profileComplete}%</div>
            <div className="stat-widget-label">Profile Complete</div>
          </div>
          <div className="stat-widget stat-widget-info" style={{ opacity: 1 }}>
            <div className="stat-widget-icon">💼</div>
            <div className="stat-widget-value">{data?.matched_job_count ?? 0}</div>
            <div className="stat-widget-label">Matched Jobs</div>
          </div>
          <div className="stat-widget stat-widget-accent" style={{ opacity: 1 }}>
            <div className="stat-widget-icon">🛠️</div>
            <div className="stat-widget-value">{data?.skill_count ?? 0}</div>
            <div className="stat-widget-label">Skills</div>
          </div>
        </div>

        {/* Profile incomplete banner */}
        {profileComplete < 50 && (
          <div className="alert alert-warning" style={{ marginBottom: '1.5rem' }}>
            Your profile is only <strong>{profileComplete}%</strong> complete.{' '}
            <Link to="/student/profile" style={{ fontWeight: 600 }}>
              Complete your profile →
            </Link>{' '}
            to unlock job recommendations and AI resume generation.
          </div>
        )}

        {/* Two Column Layout */}
        <div className="dashboard-grid-2col">
          {/* Left Column */}
          <div className="dashboard-col">
            {/* AI Placement Prediction */}
            <div className="dash-widget">
              <h3 className="dash-widget-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                🤖 AI Placement Prediction
                <details style={{ position: 'relative', display: 'inline-block' }}>
                  <summary
                    aria-label="How the placement prediction is calculated"
                    title="See prediction criteria"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '1.15rem',
                      height: '1.15rem',
                      border: '1px solid currentColor',
                      borderRadius: '50%',
                      fontSize: '0.72rem',
                      cursor: 'pointer',
                      listStyle: 'none',
                    }}
                  >
                    i
                  </summary>
                  <div
                    style={{
                      position: 'absolute',
                      zIndex: 5,
                      top: '1.6rem',
                      left: 0,
                      width: '16rem',
                      padding: '0.75rem',
                      background: 'var(--surface, #fff)',
                      border: '1px solid var(--border, #e2e8f0)',
                      borderRadius: '0.5rem',
                      boxShadow: '0 8px 24px rgba(15, 23, 42, 0.15)',
                      fontSize: '0.78rem',
                      fontWeight: 400,
                      lineHeight: 1.5,
                    }}
                  >
                    <strong>Prediction criteria</strong>
                    <div>CGPA: 30%</div>
                    <div>Skills: 25%</div>
                    <div>Projects: 20%</div>
                    <div>Certifications: 10%</div>
                    <div>Skill coverage: 15%</div>
                    <div style={{ marginTop: '0.35rem', color: 'var(--text-secondary)' }}>
                      With enough placement history, a Random Forest model uses these same five inputs.
                      Otherwise, the weighted estimate is shown.
                    </div>
                  </div>
                </details>
              </h3>
              <div className="prediction-ring-container">
                <div className="prediction-ring">
                  <svg viewBox="0 0 100 100" className="prediction-svg">
                    <circle cx="50" cy="50" r="42" fill="none" stroke="#e2e8f0" strokeWidth="8" />
                    <circle
                      cx="50" cy="50" r="42" fill="none"
                      stroke={ringColor}
                      strokeWidth="8"
                      strokeLinecap="round"
                      strokeDasharray={`${readinessScore * 2.64} 264`}
                      transform="rotate(-90 50 50)"
                    />
                  </svg>
                  <span className="prediction-ring-value">{readinessScore.toFixed(0)}%</span>
                </div>
                <div className="prediction-factors">
                  {factors.length > 0 ? (
                    factors.map((f, i) => (
                      <span key={i} className={`factor-badge factor-${f.impact}`}>
                        {f.impact === 'positive' ? '✓' : '✕'} {f.factor}
                      </span>
                    ))
                  ) : (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      Complete your profile to get a detailed prediction.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Skill Breakdown */}
            <div className="dash-widget">
              <h3 className="dash-widget-title">📈 Skill Distribution</h3>
              {data && data.skill_count > 0 ? (
                <div className="skill-bars">
                  {Object.entries(data.skill_breakdown).map(([category, count]) => (
                    <div key={category} className="skill-bar-item">
                      <div className="skill-bar-header">
                        <span>{category}</span>
                        <span className="skill-bar-count">{count}</span>
                      </div>
                      <div className="skill-bar-track">
                        <div
                          className="skill-bar-fill"
                          style={{ width: `${Math.min(100, (count / data.skill_count) * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-text">
                  No skills added yet.{' '}
                  <Link to="/student/profile">Add skills to your profile →</Link>
                </p>
              )}
            </div>
          </div>

          {/* Right Column */}
          <div className="dashboard-col">
            {/* Dream job progress */}
            <div className="dash-widget">
              <div className="dash-widget-header">
                <h3 className="dash-widget-title">🎯 Dream Job</h3>
                <Link to="/student/profile" className="dash-widget-link">Edit →</Link>
              </div>
              {data?.dream_job_progress.dream_job ? (
                <>
                  <h2 style={{ margin: '0.25rem 0 0.5rem' }}>
                    {data.dream_job_progress.dream_job}
                  </h2>
                  <p className="text-muted">
                    {data.dream_job_progress.target_job
                      ? `Closest role: ${data.dream_job_progress.target_job.title}`
                      : 'Add skills to start measuring your progress.'}
                  </p>
                  <div className="skill-bar-track" style={{ marginTop: '1rem' }}>
                    <div
                      className="skill-bar-fill"
                      style={{ width: `${data.dream_job_progress.match_score}%` }}
                    />
                  </div>
                  <p style={{ margin: '0.5rem 0 0' }}>
                    <strong>{data.dream_job_progress.match_score.toFixed(0)}%</strong> skill match
                    {' · '}
                    {data.dream_job_progress.matched_skills}/{data.dream_job_progress.required_skills} skills covered
                  </p>
                  {data.dream_job_progress.missing_skills.length > 0 && (
                    <>
                      <p className="text-muted" style={{ marginBottom: '0.5rem' }}>
                        Missing skills: {data.dream_job_progress.missing_skills.slice(0, 3).join(', ')}
                      </p>
                      {data.dream_job_progress.recommended_courses.some(
                        (group) => group.courses.length > 0
                      ) && (
                        <div style={{ marginTop: '0.75rem' }}>
                          <strong>Recommended courses</strong>
                          {data.dream_job_progress.recommended_courses
                            .filter((group) => group.courses.length > 0)
                            .slice(0, 3)
                            .map((group) => (
                              <div key={group.skill} style={{ marginTop: '0.5rem' }}>
                                <span className="text-muted">{group.skill}: </span>
                                {group.courses.slice(0, 2).map((course, index) => (
                                  <span key={course.id}>
                                    {index > 0 && ' · '}
                                    {course.url ? (
                                      <a href={course.url} target="_blank" rel="noopener noreferrer">
                                        {course.course_name}
                                      </a>
                                    ) : (
                                      course.course_name
                                    )}
                                  </span>
                                ))}
                              </div>
                            ))}
                        </div>
                      )}
                    </>
                  )}
                </>
              ) : (
                <p className="empty-text">
                  Set a dream job to get a personalized skill roadmap.{' '}
                  <Link to="/student/profile">Set your target →</Link>
                </p>
              )}
            </div>

            {/* Top Job Recommendations */}
            <div className="dash-widget">
              <div className="dash-widget-header">
                <h3 className="dash-widget-title">💼 Top Job Matches</h3>
                <Link to="/student/jobs" className="dash-widget-link">View All →</Link>
              </div>
              {data && data.top_recommendations.length > 0 ? (
                <div className="job-rec-list">
                  {data.top_recommendations.map((rec) => (
                    <div key={rec.job_role_id} className="job-rec-item">
                      <div className="job-rec-info">
                        <span className="job-rec-title">{rec.title}</span>
                        <span className="job-rec-company">{rec.company_name}</span>
                      </div>
                      <div
                        className="job-rec-score"
                        style={{
                          color:
                            rec.compatibility_score >= 70
                              ? '#10b981'
                              : rec.compatibility_score >= 40
                                ? '#f59e0b'
                                : '#ef4444',
                        }}
                      >
                        {rec.compatibility_score.toFixed(0)}%
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-text">
                  Complete your profile to get job recommendations.
                </p>
              )}
            </div>

            {/* Quick Actions */}
            <div className="dash-widget">
              <h3 className="dash-widget-title">⚡ Quick Actions</h3>
              <div className="quick-actions-grid">
                <Link to="/student/profile" className="quick-action">
                  <span className="quick-action-emoji">👤</span>
                  <span>Profile</span>
                </Link>
                <Link to="/student/resume" className="quick-action">
                  <span className="quick-action-emoji">📄</span>
                  <span>Resume</span>
                </Link>
                <Link to="/student/skills" className="quick-action">
                  <span className="quick-action-emoji">🧠</span>
                  <span>Skills</span>
                </Link>
                <Link to="/student/jobs" className="quick-action">
                  <span className="quick-action-emoji">🎯</span>
                  <span>Jobs</span>
                </Link>
                <Link to="/student/settings" className="quick-action">
                  <span className="quick-action-emoji">⚙️</span>
                  <span>Settings</span>
                </Link>
                <Link to="/student/notifications" className="quick-action">
                  <span className="quick-action-emoji">🔔</span>
                  <span>Notifications</span>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ── Sidebar ── */
interface SidebarProps {
  active: string;
  sidebarOpen: boolean;
  onToggle: () => void;
  onLogout: () => void;
}

function StudentSidebar({ active, sidebarOpen, onToggle, onLogout }: SidebarProps) {
  const { user } = useAuth();

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '🏠', path: '/student/dashboard' },
    { id: 'profile', label: 'Profile', icon: '👤', path: '/student/profile' },
    { id: 'resume', label: 'Resume', icon: '📄', path: '/student/resume' },
    { id: 'skills', label: 'Skill Analysis', icon: '🧠', path: '/student/skills' },
    { id: 'jobs', label: 'Job Matches', icon: '💼', path: '/student/jobs' },
    { id: 'notifications', label: 'Notifications', icon: '🔔', path: '/student/notifications' },
    { id: 'settings', label: 'Settings', icon: '⚙️', path: '/student/settings' },
  ];

  return (
    <>
      {sidebarOpen && <div className="sidebar-overlay" onClick={onToggle} />}
      <aside className={`student-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <Link to="/">Skill2Job</Link>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <Link
              key={item.id}
              to={item.path}
              className={`sidebar-link ${active === item.id ? 'active' : ''}`}
            >
              <span className="sidebar-link-icon">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        {/* User info + logout at bottom of sidebar */}
        <div className="sidebar-footer">
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.6rem',
            padding: '0.6rem 0.75rem',
            background: 'rgba(255,255,255,0.07)',
            borderRadius: 'var(--radius)',
            marginBottom: '0.6rem',
          }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg,#a5b4fc,#c4b5fd)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700, fontSize: '0.9rem', color: '#1e1b4b',
            }}>
              {user?.name?.charAt(0).toUpperCase() ?? '?'}
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{
                fontSize: '0.82rem', fontWeight: 600, color: 'white',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
              }}>
                {user?.name}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.55)' }}>
                Student
              </div>
            </div>
          </div>
          <button onClick={onLogout} className="sidebar-logout-btn">
            🚪 Logout
          </button>
        </div>
      </aside>
    </>
  );
}
