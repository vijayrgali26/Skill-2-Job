import { useState, useEffect, type ChangeEvent, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import api from '../../services/api';
import { useToast } from '../../components/Toast';
import { AxiosError } from 'axios';

interface ProjectEntry {
  title: string;
  description: string;
  technologies: string;
}

interface CertificationEntry {
  name: string;
  issuer: string;
  issue_date: string;
}

interface ProfileData {
  institution: string;
  degree: string;
  branch: string;
  cgpa: string;
  graduation_year: string;
  dream_job: string;
  expected_lpa: string;
  preferred_company: string;
  skills: string[];
  projects: ProjectEntry[];
  certifications: CertificationEntry[];
}

interface FieldErrors {
  institution?: string;
  degree?: string;
  branch?: string;
  cgpa?: string;
  graduation_year?: string;
  dream_job?: string;
  expected_lpa?: string;
  preferred_company?: string;
  general?: string;
}

type ProfileMode = 'choose' | 'upload' | 'manual' | 'form';

const emptyProject: ProjectEntry = { title: '', description: '', technologies: '' };
const emptyCert: CertificationEntry = { name: '', issuer: '', issue_date: '' };

export default function Profile() {
  const { showToast } = useToast();
  const [mode, setMode] = useState<ProfileMode>('choose');
  const [form, setForm] = useState<ProfileData>({
    institution: '',
    degree: '',
    branch: '',
    cgpa: '',
    graduation_year: '',
    dream_job: '',
    expected_lpa: '',
    preferred_company: '',
    skills: [],
    projects: [],
    certifications: [],
  });
  const [skillInput, setSkillInput] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resumeUploading, setResumeUploading] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [successMsg, setSuccessMsg] = useState('');
  const [fetchError, setFetchError] = useState('');
  const [hasExistingProfile, setHasExistingProfile] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await api.get('/profile');
        const d = res.data;
        setForm({
          institution: d.institution ?? '',
          degree: d.degree ?? '',
          branch: d.branch ?? '',
          cgpa: d.cgpa != null ? String(d.cgpa) : '',
          graduation_year: d.graduation_year != null ? String(d.graduation_year) : '',
          dream_job: d.dream_job ?? '',
          expected_lpa: d.expected_lpa != null ? String(d.expected_lpa) : '',
          preferred_company: d.preferred_company ?? '',
          skills: Array.isArray(d.skills_json) ? d.skills_json : (d.skills_json ? tryParseSkills(d.skills_json) : []),
          projects: Array.isArray(d.projects) ? d.projects : [],
          certifications: Array.isArray(d.certifications) ? d.certifications : [],
        });
        setHasExistingProfile(true);
        setMode('form'); // Already has profile, go straight to form
      } catch (err) {
        if (err instanceof AxiosError && err.response?.status === 404) {
          // No profile yet — show choice screen
          setMode('choose');
        } else {
          setFetchError('Failed to load profile. Please try again.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, []);

  const tryParseSkills = (raw: string): string[] => {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const validate = (): boolean => {
    const e: FieldErrors = {};
    if (!form.institution.trim()) e.institution = 'Institution is required.';
    if (!form.degree.trim()) e.degree = 'Degree is required.';
    if (!form.branch.trim()) e.branch = 'Branch is required.';

    const cgpaNum = parseFloat(form.cgpa);
    if (form.cgpa === '') {
      e.cgpa = 'CGPA is required.';
    } else if (isNaN(cgpaNum) || cgpaNum < 0.0 || cgpaNum > 10.0) {
      e.cgpa = 'CGPA must be between 0.0 and 10.0.';
    }

    if (!form.graduation_year.trim()) {
      e.graduation_year = 'Graduation year is required.';
    }

    if (form.dream_job.length > 150) {
      e.dream_job = 'Dream job must be at most 150 characters.';
    }

    if (form.expected_lpa.trim()) {
      const lpaNum = parseFloat(form.expected_lpa);
      if (isNaN(lpaNum) || lpaNum < 0.0 || lpaNum > 100.0) {
        e.expected_lpa = 'Expected LPA must be between 0.0 and 100.0.';
      }
    }

    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: FormEvent) => {
    ev.preventDefault();
    setSuccessMsg('');
    if (!validate()) return;

    setSaving(true);
    setErrors({});
    try {
      await api.put('/profile', {
        institution: form.institution,
        degree: form.degree,
        branch: form.branch,
        cgpa: parseFloat(form.cgpa),
        graduation_year: parseInt(form.graduation_year, 10),
        dream_job: form.dream_job || null,
        expected_lpa: form.expected_lpa.trim() ? parseFloat(form.expected_lpa) : null,
        preferred_company: form.preferred_company.trim() || null,
        skills: form.skills,
        projects: form.projects,
        certifications: form.certifications,
      });
      setSuccessMsg('Profile saved successfully!');
      showToast('Profile saved successfully!', 'success');
      setHasExistingProfile(true);
    } catch (err) {
      if (err instanceof AxiosError && err.response) {
        const apiErr = err.response.data?.error;
        setErrors({ general: apiErr?.message ?? 'Failed to save profile.' });
      } else {
        setErrors({ general: 'Unable to connect to the server.' });
      }
    } finally {
      setSaving(false);
    }
  };

  const handleResumeUploadAndParse = async () => {
    if (!resumeFile) {
      setErrors({ general: 'Please select a resume file.' });
      return;
    }

    setResumeUploading(true);
    setErrors({});
    setSuccessMsg('');

    try {
      const formData = new FormData();
      formData.append('resume', resumeFile);

      const res = await api.post('/resume/parse-for-profile', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const extracted = res.data.extracted_profile;

      // Pre-fill the form with extracted data
      setForm({
        institution: extracted.institution || '',
        degree: extracted.degree || '',
        branch: extracted.branch || '',
        cgpa: extracted.cgpa != null ? String(extracted.cgpa) : '',
        graduation_year: extracted.graduation_year != null ? String(extracted.graduation_year) : '',
        dream_job: '',
        expected_lpa: '',
        preferred_company: '',
        skills: Array.isArray(extracted.skills) ? extracted.skills : [],
        projects: Array.isArray(extracted.projects) ? extracted.projects : [],
        certifications: Array.isArray(extracted.certifications) ? extracted.certifications : [],
      });

      setSuccessMsg('Resume parsed successfully! Review and complete your profile below.');
      showToast('Resume parsed successfully!', 'success');
      setMode('form');
    } catch (err) {
      if (err instanceof AxiosError && err.response) {
        const apiErr = err.response.data?.error;
        setErrors({ general: apiErr?.message ?? 'Failed to parse resume.' });
      } else {
        setErrors({ general: 'Unable to connect to the server.' });
      }
    } finally {
      setResumeUploading(false);
    }
  };

  const addSkill = () => {
    const s = skillInput.trim();
    if (s && !form.skills.includes(s)) {
      setForm({ ...form, skills: [...form.skills, s] });
    }
    setSkillInput('');
  };

  const removeSkill = (idx: number) => {
    setForm({ ...form, skills: form.skills.filter((_, i) => i !== idx) });
  };

  const addProject = () => {
    setForm({ ...form, projects: [...form.projects, { ...emptyProject }] });
  };

  const updateProject = (idx: number, field: keyof ProjectEntry, value: string) => {
    const updated = form.projects.map((p, i) => (i === idx ? { ...p, [field]: value } : p));
    setForm({ ...form, projects: updated });
  };

  const removeProject = (idx: number) => {
    setForm({ ...form, projects: form.projects.filter((_, i) => i !== idx) });
  };

  const addCertification = () => {
    setForm({ ...form, certifications: [...form.certifications, { ...emptyCert }] });
  };

  const updateCert = (idx: number, field: keyof CertificationEntry, value: string) => {
    const updated = form.certifications.map((c, i) => (i === idx ? { ...c, [field]: value } : c));
    setForm({ ...form, certifications: updated });
  };

  const removeCert = (idx: number) => {
    setForm({ ...form, certifications: form.certifications.filter((_, i) => i !== idx) });
  };

  // ---- Loading state ----
  if (loading) {
    return (
      <div className="page-container">
        <p className="loading-text"><span className="spinner" /> Loading profile...</p>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="page-container">
        <div className="alert alert-error">{fetchError}</div>
        <Link to="/student/dashboard" className="back-link">Back to Dashboard</Link>
      </div>
    );
  }

  // ---- Choice Screen ----
  if (mode === 'choose') {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1 className="page-title">Create Your Profile</h1>
          <Link to="/student/dashboard" className="back-link">Back to Dashboard</Link>
        </div>

        <div className="choice-container">
          <h2 className="choice-heading">How would you like to set up your profile?</h2>
          <p className="choice-description">
            Choose one of the options below to get started.
          </p>

          <div className="choice-cards">
            <div className="choice-card" onClick={() => setMode('upload')}>
              <div className="choice-icon">📄</div>
              <h3>Upload Resume</h3>
              <p>Upload your existing resume (PDF/DOCX) and we'll automatically extract your details using AI.</p>
              <span className="choice-badge">Recommended</span>
            </div>

            <div className="choice-card" onClick={() => setMode('manual')}>
              <div className="choice-icon">✏️</div>
              <h3>Fill Manually</h3>
              <p>Enter your academic details, skills, projects, and certifications manually.</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Upload Resume Screen ----
  if (mode === 'upload') {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1 className="page-title">Upload Your Resume</h1>
          <button className="back-link" onClick={() => setMode('choose')}>← Back to Options</button>
        </div>

        {errors.general && <div className="alert alert-error">{errors.general}</div>}
        {successMsg && <div className="alert alert-success">{successMsg}</div>}

        <div className="page-section">
          <p className="helper-text">
            Upload your resume in PDF or DOCX format. Our AI will extract your skills, education,
            projects, and certifications to auto-fill your profile.
          </p>

          <div className="upload-area">
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(e: ChangeEvent<HTMLInputElement>) => setResumeFile(e.target.files?.[0] ?? null)}
              className="input"
              id="resume-upload"
            />
            {resumeFile && (
              <div className="upload-preview">
                <strong>Selected:</strong> {resumeFile.name} ({(resumeFile.size / 1024).toFixed(1)} KB)
              </div>
            )}
          </div>

          <button
            onClick={handleResumeUploadAndParse}
            disabled={resumeUploading || !resumeFile}
            className="btn btn-success btn-block mt-1"
          >
            {resumeUploading ? 'Parsing Resume...' : 'Upload & Extract Profile'}
          </button>
        </div>
      </div>
    );
  }

  // ---- Manual mode: go straight to form without resume upload ----
  if (mode === 'manual' && !hasExistingProfile) {
    setMode('form');
  }

  // ---- Profile Form (both after upload extraction and manual entry) ----
  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">My Profile</h1>
        <Link to="/student/dashboard" className="back-link">Back to Dashboard</Link>
      </div>

      {successMsg && <div className="alert alert-success">{successMsg}</div>}
      {errors.general && <div className="alert alert-error">{errors.general}</div>}

      <form onSubmit={handleSubmit} noValidate>
        {/* Academic Details */}
        <div className="page-section">
          <h2 className="section-title">Academic Details</h2>

          <div className="field">
            <label htmlFor="institution" className="label">Institution</label>
            <input id="institution" type="text" value={form.institution}
              onChange={(e) => setForm({ ...form, institution: e.target.value })}
              className={`input${errors.institution ? ' input-error' : ''}`} />
            {errors.institution && <span className="field-error">{errors.institution}</span>}
          </div>

          <div className="field">
            <label htmlFor="degree" className="label">Degree</label>
            <input id="degree" type="text" value={form.degree}
              onChange={(e) => setForm({ ...form, degree: e.target.value })}
              className={`input${errors.degree ? ' input-error' : ''}`} />
            {errors.degree && <span className="field-error">{errors.degree}</span>}
          </div>

          <div className="field">
            <label htmlFor="branch" className="label">Branch</label>
            <input id="branch" type="text" value={form.branch}
              onChange={(e) => setForm({ ...form, branch: e.target.value })}
              className={`input${errors.branch ? ' input-error' : ''}`} />
            {errors.branch && <span className="field-error">{errors.branch}</span>}
          </div>

          <div className="field-row">
            <div className="field field-flex">
              <label htmlFor="cgpa" className="label">CGPA (0.0 - 10.0)</label>
              <input id="cgpa" type="number" step="0.01" min="0" max="10" value={form.cgpa}
                onChange={(e) => setForm({ ...form, cgpa: e.target.value })}
                className={`input${errors.cgpa ? ' input-error' : ''}`} />
              {errors.cgpa && <span className="field-error">{errors.cgpa}</span>}
            </div>
            <div className="field field-flex">
              <label htmlFor="graduation_year" className="label">Graduation Year</label>
              <input id="graduation_year" type="number" value={form.graduation_year}
                onChange={(e) => setForm({ ...form, graduation_year: e.target.value })}
                className={`input${errors.graduation_year ? ' input-error' : ''}`} />
              {errors.graduation_year && <span className="field-error">{errors.graduation_year}</span>}
            </div>
          </div>
        </div>

        {/* Career Goals */}
        <div className="page-section">
          <h2 className="section-title">Career Goals</h2>
          <p className="helper-text">
            Set your dream job and expected salary to get an AI-enhanced, tailored resume.
          </p>

          <div className="field">
            <label htmlFor="dream_job" className="label">Dream Job</label>
            <input id="dream_job" type="text" value={form.dream_job}
              maxLength={150}
              placeholder="e.g., Full Stack Developer, Data Scientist"
              list="dream-job-suggestions"
              onChange={(e) => setForm({ ...form, dream_job: e.target.value })}
              className={`input${errors.dream_job ? ' input-error' : ''}`} />
            <datalist id="dream-job-suggestions">
              <option value="Full Stack Developer" />
              <option value="Frontend Developer" />
              <option value="Backend Developer" />
              <option value="Data Scientist" />
              <option value="Machine Learning Engineer" />
              <option value="Cloud Engineer" />
              <option value="DevOps Engineer" />
              <option value="Cybersecurity Analyst" />
            </datalist>
            {errors.dream_job && <span className="field-error">{errors.dream_job}</span>}
            <span className="helper-text">{form.dream_job.length}/150 characters</span>
          </div>

          <div className="field">
            <label htmlFor="expected_lpa" className="label">Expected LPA (0.0 - 100.0)</label>
            <input id="expected_lpa" type="number" step="0.1" min="0" max="100"
              value={form.expected_lpa}
              placeholder="e.g., 8.5"
              onChange={(e) => setForm({ ...form, expected_lpa: e.target.value })}
              className={`input${errors.expected_lpa ? ' input-error' : ''}`} />
            {errors.expected_lpa && <span className="field-error">{errors.expected_lpa}</span>}
          </div>

          <div className="field">
            <label htmlFor="preferred_company" className="label">Preferred Company (optional)</label>
            <input id="preferred_company" type="text" value={form.preferred_company}
              maxLength={255}
              placeholder="e.g., Google, Infosys, Microsoft"
              onChange={(e) => setForm({ ...form, preferred_company: e.target.value })}
              className={`input${errors.preferred_company ? ' input-error' : ''}`} />
            <span className="helper-text">
              We will alert you when this company posts a matching dream-job role.
            </span>
          </div>
        </div>

        {/* Skills */}
        <div className="page-section">
          <h2 className="section-title">Skills</h2>
          <div className="skill-input-row">
            <input type="text" value={skillInput}
              onChange={(e) => setSkillInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
              placeholder="Type a skill and press Enter or Add"
              className="input" />
            <button type="button" onClick={addSkill} className="btn btn-primary">Add</button>
          </div>
          <div className="tags-container">
            {form.skills.map((skill, idx) => (
              <span key={idx} className="tag-removable">
                {skill}
                <button type="button" onClick={() => removeSkill(idx)} className="tag-remove-btn">&times;</button>
              </span>
            ))}
            {form.skills.length === 0 && <p className="empty-text">No skills added yet.</p>}
          </div>
        </div>

        {/* Projects */}
        <div className="page-section">
          <h2 className="section-title">Projects</h2>
          {form.projects.map((proj, idx) => (
            <div key={idx} className="entry-card">
              <div className="entry-header">
                <strong>Project {idx + 1}</strong>
                <button type="button" onClick={() => removeProject(idx)} className="btn btn-danger btn-sm">Remove</button>
              </div>
              <div className="field">
                <label className="label">Title</label>
                <input type="text" value={proj.title}
                  onChange={(e) => updateProject(idx, 'title', e.target.value)} className="input" />
              </div>
              <div className="field">
                <label className="label">Description</label>
                <textarea value={proj.description}
                  onChange={(e) => updateProject(idx, 'description', e.target.value)}
                  className="input" />
              </div>
              <div className="field">
                <label className="label">Technologies</label>
                <input type="text" value={proj.technologies}
                  onChange={(e) => updateProject(idx, 'technologies', e.target.value)} className="input" />
              </div>
            </div>
          ))}
          <button type="button" onClick={addProject} className="btn btn-primary">+ Add Project</button>
        </div>

        {/* Certifications */}
        <div className="page-section">
          <h2 className="section-title">Certifications</h2>
          {form.certifications.map((cert, idx) => (
            <div key={idx} className="entry-card">
              <div className="entry-header">
                <strong>Certification {idx + 1}</strong>
                <button type="button" onClick={() => removeCert(idx)} className="btn btn-danger btn-sm">Remove</button>
              </div>
              <div className="field">
                <label className="label">Name</label>
                <input type="text" value={cert.name}
                  onChange={(e) => updateCert(idx, 'name', e.target.value)} className="input" />
              </div>
              <div className="field">
                <label className="label">Issuer</label>
                <input type="text" value={cert.issuer}
                  onChange={(e) => updateCert(idx, 'issuer', e.target.value)} className="input" />
              </div>
              <div className="field">
                <label className="label">Issue Date</label>
                <input type="date" value={cert.issue_date}
                  onChange={(e) => updateCert(idx, 'issue_date', e.target.value)} className="input" />
              </div>
            </div>
          ))}
          <button type="button" onClick={addCertification} className="btn btn-primary">+ Add Certification</button>
        </div>

        <button type="submit" disabled={saving} className="btn btn-success btn-block mt-1">
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </form>
    </div>
  );
}
