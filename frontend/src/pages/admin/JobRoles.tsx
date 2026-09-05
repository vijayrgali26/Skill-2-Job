import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';

interface Company {
  id: number;
  name: string;
}

interface JobRole {
  id: number;
  company_id: number;
  title: string;
  description: string | null;
  required_skills_json: string | null;
  cgpa_threshold: number | null;
  salary_lpa_min: number | null;
  academic_status: string | null;
  is_active: boolean;
  created_at: string | null;
}

interface JobForm {
  company_id: string;
  title: string;
  description: string;
  required_skills: string;
  cgpa_threshold: string;
  salary_lpa_min: string;
  academic_status: string;
}

const emptyForm: JobForm = {
  company_id: '',
  title: '',
  description: '',
  required_skills: '',
  cgpa_threshold: '0',
  salary_lpa_min: '',
  academic_status: '',
};

export default function JobRoles() {
  const { logout } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [jobs, setJobs] = useState<JobRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState<JobForm>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [compRes, jobRes] = await Promise.all([
        api.get('/admin/companies'),
        api.get('/admin/companies'), // We'll derive jobs from companies
      ]);
      setCompanies(compRes.data);
      setError('');
      void jobRes; // suppress unused
    } catch {
      setError('Failed to load data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const parseSkills = (raw: string): string[] =>
    raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (!form.company_id) {
      setFormError('Please select a company.');
      return;
    }
    if (!form.title.trim()) {
      setFormError('Job title is required.');
      return;
    }

    const payload = {
      company_id: Number(form.company_id),
      title: form.title.trim(),
      description: form.description.trim() || null,
      required_skills: parseSkills(form.required_skills),
      cgpa_threshold: parseFloat(form.cgpa_threshold) || 0,
      salary_lpa_min: form.salary_lpa_min.trim() ? parseFloat(form.salary_lpa_min) : null,
      academic_status: form.academic_status.trim() || null,
    };

    setSaving(true);
    try {
      if (editingId) {
        const res = await api.put(`/admin/jobs/${editingId}`, payload);
        setJobs((prev) =>
          prev.map((j) => (j.id === editingId ? res.data : j))
        );
      } else {
        const res = await api.post('/admin/jobs', payload);
        setJobs((prev) => [...prev, res.data]);
      }
      setForm(emptyForm);
      setEditingId(null);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message || 'Failed to save job role.';
      setFormError(msg);
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (j: JobRole) => {
    let skills = '';
    if (j.required_skills_json) {
      try {
        const arr = JSON.parse(j.required_skills_json);
        if (Array.isArray(arr)) skills = arr.join(', ');
      } catch {
        skills = '';
      }
    }
    setEditingId(j.id);
    setForm({
      company_id: String(j.company_id),
      title: j.title,
      description: j.description || '',
      required_skills: skills,
      cgpa_threshold: String(j.cgpa_threshold ?? 0),
      salary_lpa_min: j.salary_lpa_min != null ? String(j.salary_lpa_min) : '',
      academic_status: j.academic_status || '',
    });
    setFormError('');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormError('');
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this job role?')) return;
    try {
      await api.delete(`/admin/jobs/${id}`);
      setJobs((prev) => prev.filter((j) => j.id !== id));
    } catch {
      setError('Failed to delete job role.');
    }
  };

  const companyName = (id: number) =>
    companies.find((c) => c.id === id)?.name || `Company #${id}`;

  const renderSkills = (json: string | null) => {
    if (!json) return '—';
    try {
      const arr = JSON.parse(json);
      return Array.isArray(arr) ? arr.join(', ') : '—';
    } catch {
      return '—';
    }
  };

  return (
    <div className="page-container-wide">
      <div className="page-header">
        <h1 className="page-title">Job Role Management</h1>
        <div className="page-header-actions">
          <Link to="/admin/dashboard" className="back-link">
            ← Dashboard
          </Link>
          <button onClick={logout} className="dash-logout-btn">
            Logout
          </button>
        </div>
      </div>

      {/* Add / Edit Form */}
      <div className="form-card">
        <h2 className="form-title">
          {editingId ? 'Edit Job Role' : 'Add Job Role'}
        </h2>
        {formError && <p className="error-text">{formError}</p>}
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="label-col">
              Company *
              <select
                name="company_id"
                value={form.company_id}
                onChange={handleChange}
                className="input"
                required
              >
                <option value="">Select company</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="label-col">
              Title *
              <input
                name="title"
                value={form.title}
                onChange={handleChange}
                className="input"
                required
              />
            </label>
            <label className="label-col">
              CGPA Threshold
              <input
                name="cgpa_threshold"
                value={form.cgpa_threshold}
                onChange={handleChange}
                className="input"
                type="number"
                step="0.1"
                min="0"
                max="10"
              />
            </label>
            <label className="label-col">
              Academic Status
              <input
                name="academic_status"
                value={form.academic_status}
                onChange={handleChange}
                className="input"
                placeholder="e.g. Final Year"
              />
            </label>
            <label className="label-col">
              Minimum Package (LPA)
              <input
                name="salary_lpa_min"
                value={form.salary_lpa_min}
                onChange={handleChange}
                className="input"
                type="number"
                step="0.1"
                min="0"
                max="100"
                placeholder="Optional"
              />
            </label>
          </div>
          <label className="label-col mt-1">
            Required Skills (comma-separated)
            <input
              name="required_skills"
              value={form.required_skills}
              onChange={handleChange}
              className="input"
              placeholder="Python, React, SQL"
            />
          </label>
          <label className="label-col mt-1">
            Description
            <textarea
              name="description"
              value={form.description}
              onChange={handleChange}
              className="input"
            />
          </label>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : editingId ? 'Update' : 'Add Job Role'}
            </button>
            {editingId && (
              <button
                type="button"
                onClick={cancelEdit}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Job List */}
      {loading ? (
        <p className="loading-text"><span className="spinner" /> Loading...</p>
      ) : error ? (
        <p className="error-text">{error}</p>
      ) : jobs.length === 0 ? (
        <p className="empty-text">No job roles yet. Add one above.</p>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Company</th>
                <th>Skills</th>
                <th>CGPA</th>
                <th>Active</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.title}</td>
                  <td>{companyName(j.company_id)}</td>
                  <td>{renderSkills(j.required_skills_json)}</td>
                  <td>{j.cgpa_threshold ?? '—'}</td>
                  <td>{j.is_active ? 'Yes' : 'No'}</td>
                  <td>
                    <span className="flex gap-1">
                      <button onClick={() => startEdit(j)} className="btn btn-warning btn-sm">
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(j.id)}
                        className="btn btn-danger btn-sm"
                      >
                        Delete
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
