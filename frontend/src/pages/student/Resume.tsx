import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { AxiosError } from 'axios';
import api from '../../services/api';
import { useToast } from '../../components/Toast';

interface ResumeUploadEntry {
  id: number; original_filename: string; content_type: string; uploaded_at: string;
}
interface ProfileData {
  institution?: string; degree?: string; branch?: string;
  cgpa?: number; graduation_year?: number; skills_json?: string;
  dream_job?: string; name?: string;
}

// ── Template definitions ────────────────────────────────────────────────────
const TEMPLATES = [
  {
    id: 'classic', name: 'Classic', hasPhoto: false, color: '#1a237e',
    desc: 'ATS-friendly professional layout with clear sections and blue headers',
    preview: ['▬▬▬▬▬▬▬▬▬▬▬', '━━━━━━━━━━━━━━━━━━━━', '▪ Education', '▪ Skills', '▪ Projects'],
  },
  {
    id: 'sidebar', name: 'Sidebar', hasPhoto: true, color: '#1e293b',
    desc: 'Professional photo layout with an ATS-readable content column',
    preview: ['◑ SIDEBAR + CONTENT', '██ Contact', '██ Skills', '  │ Objective', '  │ Projects'],
  },
];

const REQUIRED = [
  { key: 'institution', label: 'Institution / College Name', type: 'text', placeholder: 'e.g. ATMECE, Mysore' },
  { key: 'degree', label: 'Degree', type: 'text', placeholder: 'e.g. B.E' },
  { key: 'branch', label: 'Branch / Specialization', type: 'text', placeholder: 'e.g. Computer Science' },
  { key: 'cgpa', label: 'CGPA', type: 'number', placeholder: 'e.g. 8.5' },
  { key: 'graduation_year', label: 'Graduation Year', type: 'number', placeholder: 'e.g. 2026' },
  { key: 'skills_json', label: 'Skills (comma separated)', type: 'text', placeholder: 'Python, React, MySQL' },
];

export default function Resume() {
  const { showToast } = useToast();
  const [selectedTemplate, setSelectedTemplate] = useState('classic');
  const [step, setStep] = useState<'pick' | 'check' | 'fill' | 'done'>('pick');
  const [profile, setProfile] = useState<ProfileData>({});
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [fillData, setFillData] = useState<Record<string, string>>({});
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [atsScore, setAtsScore] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploads, setUploads] = useState<ResumeUploadEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/resume/uploads').then(r => setUploads(r.data.uploads ?? [])).catch(() => { });
    api.get('/profile').then(r => setProfile(r.data)).catch(() => { });
  }, []);

  // Check profile completeness when user clicks Generate
  const handleCheckProfile = () => {
    const missing: string[] = [];
    if (!profile.institution) missing.push('institution');
    if (!profile.degree) missing.push('degree');
    if (!profile.branch) missing.push('branch');
    const skills = profile.skills_json;
    const hasSkills = skills && (
      (typeof skills === 'string' && JSON.parse(skills || '[]').length > 0) ||
      (Array.isArray(skills) && skills.length > 0)
    );
    if (!hasSkills) missing.push('skills_json');

    if (missing.length > 0) {
      setMissingFields(missing);
      setStep('check');
    } else {
      doGenerate({});
    }
  };

  const doGenerate = async (overrides: Record<string, string>) => {
    setGenerating(true); setError(''); setStep('done');
    // Build profile override — convert skills string to JSON array
    const po: Record<string, unknown> = { ...overrides };
    if (po.skills_json && typeof po.skills_json === 'string') {
      po.skills_json = JSON.stringify(
        (po.skills_json as string).split(',').map((s: string) => s.trim()).filter(Boolean)
      );
    }
    try {
      const response = await api.post('/resume/generate', { template: selectedTemplate, profile_override: po });
      setAtsScore(response.data.ats_score ?? null);
      showToast('Resume generated!', 'success');
    } catch (err) {
      const msg = err instanceof AxiosError ? err.response?.data?.error?.message ?? 'Failed' : 'Connection error';
      setError(msg); setStep('pick');
    } finally { setGenerating(false); }
  };

  const handleFillSubmit = (e: FormEvent) => {
    e.preventDefault();
    doGenerate(fillData);
  };

  const handleDownload = async () => {
    setDownloading(true); setError('');
    try {
      const res = await api.get(`/resume/download?template=${selectedTemplate}`, { responseType: 'blob' });
      const score = res.headers['x-ats-score'];
      if (score) setAtsScore(Number(score));
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a'); a.href = url; a.download = 'resume.pdf';
      document.body.appendChild(a); a.click();
      window.URL.revokeObjectURL(url); document.body.removeChild(a);
    } catch { setError('Download failed. Please generate first.'); }
    finally { setDownloading(false); }
  };

  const handleUpload = async () => {
    if (!selectedFile) { setError('Please select a file.'); return; }
    setUploading(true);
    try {
      const fd = new FormData(); fd.append('resume', selectedFile);
      const response = await api.post('/resume/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (response.data.profile) setProfile(response.data.profile);
      const refreshedProfile = await api.get('/profile');
      setProfile(refreshedProfile.data);
      showToast('Uploaded!', 'success'); setSelectedFile(null);
      api.get('/resume/uploads').then(r => setUploads(r.data.uploads ?? []));
    } catch { setError('Upload failed.'); }
    finally { setUploading(false); }
  };

  const handleUploadedDownload = async (id: number, name: string) => {
    try {
      const res = await api.get(`/resume/uploads/${id}/download`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a'); a.href = url; a.download = name;
      document.body.appendChild(a); a.click();
      window.URL.revokeObjectURL(url); document.body.removeChild(a);
    } catch { setError('Download failed.'); }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">📄 Resume Builder</h1>
        <Link to="/student/dashboard" className="back-link">← Dashboard</Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* ── STEP 1: Template Picker ─────────────────────────────── */}
      {(step === 'pick' || step === 'done') && (
        <div className="page-section">
          <h2 className="section-title">Choose a Template</h2>
          <p className="muted-text" style={{ marginBottom: '1.25rem' }}>
            Select a style that suits you. Templates with 📷 include a photo/initials circle.
          </p>

          <div style={{
            display: 'flex', flexDirection: 'row', flexWrap: 'wrap',
            gap: '1rem', marginBottom: '1.5rem'
          }}>
            {TEMPLATES.map(t => (
              <TemplateCard key={t.id} t={t}
                selected={selectedTemplate === t.id}
                onSelect={() => setSelectedTemplate(t.id)} />
            ))}
          </div>

          {/* Action buttons */}
          <div className="btn-row">
            <button onClick={handleCheckProfile} disabled={generating} className="btn btn-primary" style={{ minWidth: '160px' }}>
              {generating ? 'Generating...' : '⚡ Generate Resume'}
            </button>
            {step === 'done' && (
              <>
                <button onClick={handleDownload} disabled={downloading} className="btn btn-success">
                  {downloading ? 'Downloading...' : '⬇ Download PDF'}
                </button>
                {atsScore !== null && (
                  <span className="alert alert-success" style={{ margin: 0 }}>
                    ATS score: <strong>{atsScore}/100</strong>
                  </span>
                )}
              </>
            )}
          </div>

          {profile.dream_job && (
            <p className="alert alert-success" style={{ marginTop: '1rem' }}>
              ✨ <strong>AI-Enhanced</strong> — tailored for your dream job: <strong>{profile.dream_job}</strong>
            </p>
          )}
        </div>
      )}

      {/* ── STEP 2: Profile Warning Modal ──────────────────────── */}
      {step === 'check' && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
        }}>
          <div style={{
            background: 'var(--surface)', borderRadius: 'var(--radius-xl)',
            padding: '2rem', maxWidth: '480px', width: '90%',
            boxShadow: 'var(--shadow-xl)', animation: 'fadeIn 0.2s ease',
          }}>
            <div style={{ fontSize: '2.5rem', textAlign: 'center', marginBottom: '0.5rem' }}>⚠️</div>
            <h2 style={{ textAlign: 'center', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
              Profile Incomplete
            </h2>
            <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
              The following fields are missing from your profile:
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', justifyContent: 'center', marginBottom: '1.5rem' }}>
              {missingFields.map(f => {
                const req = REQUIRED.find(r => r.key === f);
                return (
                  <span key={f} style={{
                    background: 'var(--danger-light)', color: 'var(--danger)',
                    padding: '3px 12px', borderRadius: 'var(--radius-pill)',
                    fontSize: '0.82rem', fontWeight: 600,
                    border: '1px solid rgba(239,68,68,0.3)',
                  }}>
                    {req?.label || f}
                  </span>
                );
              })}
            </div>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                onClick={() => { setStep('fill'); }}
                className="btn btn-primary"
                style={{ flex: 1 }}
              >
                ✏️ Fill Missing Fields
              </button>
              <button
                onClick={() => doGenerate({})}
                className="btn btn-secondary"
                style={{ flex: 1 }}
                disabled={generating}
              >
                {generating ? 'Generating...' : 'Skip & Generate'}
              </button>
            </div>
            <button
              onClick={() => setStep('pick')}
              style={{
                marginTop: '0.75rem', width: '100%', background: 'none',
                border: 'none', color: 'var(--text-secondary)', cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Fill Missing Fields Form Modal ─────────────── */}
      {step === 'fill' && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
          padding: '1rem',
        }}>
          <div style={{
            background: 'var(--surface)', borderRadius: 'var(--radius-xl)',
            padding: '2rem', maxWidth: '500px', width: '100%',
            boxShadow: 'var(--shadow-xl)', maxHeight: '90vh', overflowY: 'auto',
            animation: 'fadeIn 0.2s ease',
          }}>
            <h2 style={{ marginBottom: '0.25rem', color: 'var(--text-primary)' }}>
              ✏️ Complete Your Profile
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
              Fill in the missing fields below. These will be used only for this resume.
              To save permanently, update your <Link to="/student/profile" style={{ color: 'var(--primary)' }}>profile page</Link>.
            </p>
            <form onSubmit={handleFillSubmit}>
              {missingFields.map(fk => {
                const req = REQUIRED.find(r => r.key === fk);
                if (!req) return null;
                return (
                  <div key={fk} className="field">
                    <label className="label">{req.label} <span style={{ color: 'var(--danger)' }}>*</span></label>
                    <input
                      type={req.type}
                      step={req.type === 'number' ? '0.01' : undefined}
                      className="input"
                      placeholder={req.placeholder}
                      value={fillData[fk] ?? ''}
                      onChange={e => setFillData(prev => ({ ...prev, [fk]: e.target.value }))}
                      required
                    />
                    {fk === 'skills_json' && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        Separate skills with commas
                      </span>
                    )}
                  </div>
                );
              })}
              <div className="btn-row" style={{ marginTop: '1.25rem' }}>
                <button type="submit" disabled={generating} className="btn btn-primary" style={{ flex: 1 }}>
                  {generating ? 'Generating...' : '⚡ Generate Now'}
                </button>
                <button type="button" onClick={() => setStep('check')} className="btn btn-secondary">
                  Back
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Upload Section ─────────────────────────────────────── */}
      <div className="page-section">
        <div className="card">
          <h2 className="card-title">📤 Upload Existing Resume</h2>
          <p className="card-desc">Upload a PDF or DOCX resume to store it alongside the generated one.</p>
          <div className="resume-upload-row">
            <input type="file" accept=".pdf,.docx" onChange={(e: ChangeEvent<HTMLInputElement>) => setSelectedFile(e.target.files?.[0] ?? null)} className="input" />
            <button onClick={handleUpload} disabled={uploading} className="btn btn-secondary">
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </div>
          {selectedFile && <p className="muted-text">Selected: {selectedFile.name}</p>}
        </div>
      </div>

      {/* ── Upload History ─────────────────────────────────────── */}
      {uploads.length > 0 && (
        <div className="page-section">
          <h2 className="section-title">Upload History</h2>
          <div className="table-wrapper">
            <table className="table">
              <thead><tr><th>File</th><th>Type</th><th>Uploaded</th><th>Action</th></tr></thead>
              <tbody>
                {uploads.map(u => (
                  <tr key={u.id}>
                    <td>{u.original_filename}</td>
                    <td>{u.content_type}</td>
                    <td>{new Date(u.uploaded_at).toLocaleString()}</td>
                    <td>
                      <button className="btn btn-sm btn-secondary"
                        onClick={() => handleUploadedDownload(u.id, u.original_filename)}>
                        Download
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Template Card Component ─────────────────────────────────────────────────
function TemplateCard({ t, selected, onSelect }: {
  t: typeof TEMPLATES[0]; selected: boolean; onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      style={{
        border: `2px solid ${selected ? t.color : 'var(--border)'}`,
        borderRadius: 'var(--radius-lg)',
        padding: '0.75rem',
        cursor: 'pointer',
        background: selected ? `${t.color}08` : 'var(--surface)',
        transition: 'all 0.2s ease',
        boxShadow: selected ? `0 0 0 3px ${t.color}30` : 'var(--shadow-xs)',
        position: 'relative',
        flex: '1 1 280px',
        minWidth: 0,
      }}
    >
      {/* Selected checkmark */}
      {selected && (
        <div style={{
          position: 'absolute', top: '8px', right: '8px',
          width: '20px', height: '20px', borderRadius: '50%',
          background: t.color, display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: 'white', fontSize: '11px', fontWeight: 700,
        }}>✓</div>
      )}

      {/* Mini preview */}
      <div style={{
        background: '#f8fafc', borderRadius: '6px', padding: '0.5rem',
        marginBottom: '0.6rem', fontFamily: 'monospace', fontSize: '7px',
        lineHeight: '1.5', color: '#64748b', minHeight: '70px',
        borderLeft: `3px solid ${t.color}`,
      }}>
        {t.preview.map((line, i) => (
          <div key={i} style={{ color: i === 0 ? t.color : '#64748b', fontWeight: i === 0 ? 700 : 400 }}>
            {line}
          </div>
        ))}
      </div>

      {/* Name + badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ fontWeight: 700, fontSize: '0.85rem', color: selected ? t.color : 'var(--text-primary)' }}>
          {t.name}
        </span>
        {t.hasPhoto && (
          <span style={{
            fontSize: '0.65rem', background: `${t.color}18`, color: t.color,
            padding: '1px 6px', borderRadius: '10px', fontWeight: 600,
          }}>📷</span>
        )}
      </div>
      <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>
        {t.desc}
      </p>
    </div>
  );
}
