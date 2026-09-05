import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import { useToast } from '../components/Toast';
import {
    BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

// ── Types ────────────────────────────────────────────────────────────────────
interface Overview {
    total_students: number; placed_students: number; placement_percentage: number;
    total_companies: number; avg_package: number; max_package: number;
}
interface YearlyTrend {
    year: number; placed: number; total: number; rate: number; avg_package: number;
}
interface BranchRow { branch: string; placed: number; total: number; rate: number; }
interface CompanyRow { company: string; industry: string; count: number; avg_package: number; }
interface RoleRow { role: string; count: number; }
interface PkgRow { range: string; count: number; }
interface CampusData { on_campus: number; off_campus: number; }
interface PlacedStudent {
    name: string; branch: string; cgpa: number | null; graduation_year: number;
    company: string; role: string; package_lpa: number | null;
    campus_type: string; placement_date: string | null;
}
interface StatsData {
    overview: Overview; yearly_trend: YearlyTrend[];
    branch_breakdown: BranchRow[]; company_breakdown: CompanyRow[];
    on_off_campus: CampusData; top_roles: RoleRow[];
    package_distribution: PkgRow[]; placed_students: PlacedStudent[];
}

const COLORS = ['#4f46e5', '#0d9488', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6', '#ec4899', '#06b6d4'];
const BRANCH_COLORS: Record<string, string> = {
    'Computer Science': '#4f46e5', 'Information Science': '#0d9488',
    'Electronics': '#f59e0b', 'Mechanical': '#ef4444',
    'Civil': '#10b981', 'Electrical': '#8b5cf6',
};

export default function Stats() {
    const { user, logout } = useAuth();
    const { showToast } = useToast();
    const navigate = useNavigate();
    const [data, setData] = useState<StatsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [yearFilter, setYearFilter] = useState<string>('');
    const [search, setSearch] = useState('');
    const [campusFilter, setCampusFilter] = useState<'all' | 'On-Campus' | 'Off-Campus'>('all');

    const isStudent = user?.role === 'student';

    const fetchStats = useCallback(async () => {
        setLoading(true);
        try {
            const params: Record<string, string> = {};
            if (yearFilter) params.year = yearFilter;
            const res = await api.get('/stats', { params });
            setData(res.data);
        } catch {
            showToast('Failed to load statistics', 'error');
        } finally {
            setLoading(false);
        }
    }, [yearFilter]);

    useEffect(() => { fetchStats(); }, [fetchStats]);

    const handleLogout = () => { logout(); navigate('/login'); };

    const filteredStudents = (data?.placed_students ?? []).filter(s => {
        const matchSearch = !search ||
            s.name.toLowerCase().includes(search.toLowerCase()) ||
            s.branch.toLowerCase().includes(search.toLowerCase()) ||
            s.company.toLowerCase().includes(search.toLowerCase()) ||
            s.role.toLowerCase().includes(search.toLowerCase());
        const matchCampus = campusFilter === 'all' || s.campus_type === campusFilter;
        return matchSearch && matchCampus;
    });

    const backPath = isStudent ? '/student/dashboard' : '/admin/dashboard';
    const backLabel = isStudent ? '← Student Dashboard' : '← Dashboard';

    return (
        <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
            {/* Header */}
            <div style={{
                background: 'linear-gradient(135deg, #1e293b 0%, #334155 100%)',
                padding: '1.5rem 2rem', display: 'flex', alignItems: 'center',
                justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem',
            }}>
                <div>
                    <h1 style={{ color: 'white', fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>
                        📊 Placement Statistics
                    </h1>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: '4px 0 0' }}>
                        ATMECE — Placement Data 2021–2025
                    </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <Link to={backPath} style={{ color: '#94a3b8', fontSize: '0.85rem', textDecoration: 'none' }}>
                        {backLabel}
                    </Link>
                    <button onClick={handleLogout} style={{
                        background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.4)',
                        color: '#fca5a5', padding: '0.4rem 1rem', borderRadius: '8px',
                        cursor: 'pointer', fontSize: '0.82rem',
                    }}>Logout</button>
                </div>
            </div>

            <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '2rem 1.5rem' }}>
                {/* Year filter */}
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
                    {['', '2021', '2022', '2023', '2024', '2025'].map(y => (
                        <button key={y} onClick={() => setYearFilter(y)}
                            style={{
                                padding: '0.5rem 1.2rem', borderRadius: '20px',
                                cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem', transition: 'all 0.2s',
                                background: yearFilter === y ? '#4f46e5' : 'var(--surface)',
                                color: yearFilter === y ? 'white' : 'var(--text-secondary)',
                                boxShadow: yearFilter === y ? '0 2px 8px rgba(79,70,229,0.3)' : 'var(--shadow-xs)',
                                border: yearFilter === y ? 'none' : '1px solid var(--border)',
                            }}>
                            {y === '' ? 'All Years' : y}
                        </button>
                    ))}
                    {loading && <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', alignSelf: 'center' }}>
                        Loading...
                    </span>}
                </div>

                {data && (
                    <>
                        {/* ── Overview Cards ─────────────────────────────────── */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
                            {[
                                { label: 'Total Students', value: data.overview.total_students.toLocaleString(), icon: '👨‍🎓', color: '#4f46e5' },
                                { label: 'Placed Students', value: data.overview.placed_students.toLocaleString(), icon: '✅', color: '#10b981' },
                                { label: 'Placement Rate', value: `${data.overview.placement_percentage}%`, icon: '📈', color: '#f59e0b' },
                                { label: 'Companies', value: data.overview.total_companies.toLocaleString(), icon: '🏢', color: '#0d9488' },
                                { label: 'Avg Package', value: `₹${data.overview.avg_package} LPA`, icon: '💰', color: '#8b5cf6' },
                                { label: 'Highest Package', value: `₹${data.overview.max_package} LPA`, icon: '🏆', color: '#ec4899' },
                            ].map(c => (
                                <div key={c.label} style={{
                                    background: 'var(--surface)', borderRadius: '14px', padding: '1.25rem',
                                    border: `1px solid var(--border)`, textAlign: 'center',
                                    borderTop: `4px solid ${c.color}`,
                                }}>
                                    <div style={{ fontSize: '1.6rem', marginBottom: '0.4rem' }}>{c.icon}</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: c.color }}>{c.value}</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{c.label}</div>
                                </div>
                            ))}
                        </div>

                        {/* ── Yearly Trend ─────────────────────────────────── */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                            <ChartCard title="📅 Year-wise Placement Count">
                                <ResponsiveContainer width="100%" height={240}>
                                    <BarChart data={data.yearly_trend}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                        <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                                        <YAxis tick={{ fontSize: 12 }} />
                                        <Tooltip />
                                        <Legend />
                                        <Bar dataKey="total" name="Total Students" fill="#e0e7ff" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="placed" name="Placed" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>

                            <ChartCard title="📊 Year-wise Placement Rate (%)">
                                <ResponsiveContainer width="100%" height={240}>
                                    <LineChart data={data.yearly_trend}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                        <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                                        <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                                        <Tooltip formatter={(v: number) => `${v}%`} />
                                        <Legend />
                                        <Line type="monotone" dataKey="rate" name="Placement %" stroke="#4f46e5"
                                            strokeWidth={3} dot={{ r: 5 }} />
                                        <Line type="monotone" dataKey="avg_package" name="Avg Pkg (LPA)"
                                            stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} strokeDasharray="5 5" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </div>

                        {/* ── Branch + Campus ───────────────────────────────── */}
                        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                            <ChartCard title="🎓 Branch-wise Placements">
                                <ResponsiveContainer width="100%" height={260}>
                                    <BarChart data={data.branch_breakdown} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                        <XAxis type="number" tick={{ fontSize: 11 }} />
                                        <YAxis dataKey="branch" type="category" width={130} tick={{ fontSize: 11 }} />
                                        <Tooltip />
                                        <Legend />
                                        <Bar dataKey="total" name="Total" fill="#e0e7ff" radius={[0, 4, 4, 0]} />
                                        <Bar dataKey="placed" name="Placed" fill="#4f46e5" radius={[0, 4, 4, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>

                            <ChartCard title="🏫 On-Campus vs Off-Campus">
                                <ResponsiveContainer width="100%" height={260}>
                                    <PieChart>
                                        <Pie
                                            data={[
                                                { name: 'On-Campus', value: data.on_off_campus.on_campus },
                                                { name: 'Off-Campus', value: data.on_off_campus.off_campus },
                                            ]}
                                            cx="50%" cy="50%" outerRadius={90} dataKey="value" label
                                        >
                                            <Cell fill="#4f46e5" />
                                            <Cell fill="#10b981" />
                                        </Pie>
                                        <Tooltip />
                                        <Legend />
                                    </PieChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </div>

                        {/* ── Package Distribution + Top Roles ─────────────── */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                            <ChartCard title="💰 Package Distribution">
                                <ResponsiveContainer width="100%" height={240}>
                                    <BarChart data={data.package_distribution}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                        <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 12 }} />
                                        <Tooltip />
                                        <Bar dataKey="count" name="Students" radius={[4, 4, 0, 0]}>
                                            {data.package_distribution.map((_, i) => (
                                                <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>

                            <ChartCard title="💼 Top Job Roles">
                                <ResponsiveContainer width="100%" height={240}>
                                    <BarChart data={data.top_roles} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                        <XAxis type="number" tick={{ fontSize: 11 }} />
                                        <YAxis dataKey="role" type="category" width={150} tick={{ fontSize: 10 }} />
                                        <Tooltip />
                                        <Bar dataKey="count" name="Placed" fill="#0d9488" radius={[0, 4, 4, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </div>

                        {/* ── Top Companies Table ───────────────────────────── */}
                        <ChartCard title="🏢 Top Recruiting Companies" style={{ marginBottom: '2rem' }}>
                            <div className="table-wrapper">
                                <table className="table">
                                    <thead>
                                        <tr><th>#</th><th>Company</th><th>Industry</th><th>Students Placed</th><th>Avg Package</th></tr>
                                    </thead>
                                    <tbody>
                                        {data.company_breakdown.map((c, i) => (
                                            <tr key={c.company}>
                                                <td style={{ fontWeight: 700, color: '#4f46e5' }}>{i + 1}</td>
                                                <td style={{ fontWeight: 600 }}>{c.company}</td>
                                                <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{c.industry}</td>
                                                <td>
                                                    <span style={{
                                                        background: '#e0e7ff', color: '#4f46e5', padding: '2px 10px',
                                                        borderRadius: '12px', fontWeight: 700, fontSize: '0.85rem'
                                                    }}>
                                                        {c.count}
                                                    </span>
                                                </td>
                                                <td style={{ color: '#10b981', fontWeight: 600 }}>₹{c.avg_package} LPA</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </ChartCard>

                        {/* ── Placed Students Table ────────────────────────── */}
                        <ChartCard title={`👨‍💼 Placed Students (${filteredStudents.length})`}>
                            {/* Search + filter bar */}
                            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                                <input
                                    type="text" placeholder="Search by name, branch, company, role..."
                                    value={search} onChange={e => setSearch(e.target.value)}
                                    className="input" style={{ flex: 1, minWidth: '200px' }}
                                />
                                {(['all', 'On-Campus', 'Off-Campus'] as const).map(f => (
                                    <button key={f} onClick={() => setCampusFilter(f)}
                                        className={`btn ${campusFilter === f ? 'btn-primary' : 'btn-secondary'} btn-sm`}>
                                        {f === 'all' ? 'All' : f}
                                    </button>
                                ))}
                            </div>

                            <div className="table-wrapper">
                                <table className="table">
                                    <thead>
                                        <tr>
                                            <th>Student Name</th><th>Branch</th><th>CGPA</th><th>Batch</th>
                                            <th>Company</th><th>Role</th><th>Package</th><th>Type</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredStudents.length === 0 ? (
                                            <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '2rem' }}>
                                                No records found
                                            </td></tr>
                                        ) : filteredStudents.map((s, i) => (
                                            <tr key={i}>
                                                <td style={{ fontWeight: 600 }}>{s.name}</td>
                                                <td>
                                                    <span style={{
                                                        background: `${BRANCH_COLORS[s.branch] || '#6b7280'}18`,
                                                        color: BRANCH_COLORS[s.branch] || '#6b7280',
                                                        padding: '2px 8px', borderRadius: '10px', fontSize: '0.8rem', fontWeight: 600,
                                                    }}>{s.branch}</span>
                                                </td>
                                                <td>{s.cgpa?.toFixed(2) ?? '—'}</td>
                                                <td>{s.graduation_year}</td>
                                                <td style={{ fontWeight: 500 }}>{s.company}</td>
                                                <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{s.role}</td>
                                                <td style={{ color: '#10b981', fontWeight: 700 }}>
                                                    {s.package_lpa ? `₹${s.package_lpa} LPA` : '—'}
                                                </td>
                                                <td>
                                                    <span style={{
                                                        background: s.campus_type === 'On-Campus' ? '#d1fae5' : '#dbeafe',
                                                        color: s.campus_type === 'On-Campus' ? '#065f46' : '#1e40af',
                                                        padding: '2px 8px', borderRadius: '10px', fontSize: '0.78rem', fontWeight: 600,
                                                    }}>{s.campus_type}</span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </ChartCard>
                    </>
                )}
            </div>
        </div>
    );
}

function ChartCard({ title, children, style }: {
    title: string; children: React.ReactNode; style?: React.CSSProperties;
}) {
    return (
        <div style={{
            background: 'var(--surface)', borderRadius: '16px', padding: '1.25rem',
            border: '1px solid var(--border)', boxShadow: 'var(--shadow-xs)', ...style,
        }}>
            <h3 style={{
                fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)',
                marginBottom: '1rem', marginTop: 0
            }}>{title}</h3>
            {children}
        </div>
    );
}
