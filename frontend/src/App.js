import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
import './App.css';
import PhysioAI from './components/PhysioAIv2';
import NutriAI from './components/NutriAI';
import Chatbot from './components/Chatbot';
import MonitoringDashboard from './components/MonitoringDashboard';
import Login from './components/Login';
import { restoreSession, logout, setupAxios } from './auth';

// Attach JWT interceptor once at module level
setupAxios(axios);

const MODULES = [
  { key: 'home',    label: 'Dashboard',  icon: '🏠', cls: '', roles: ['all'] },
  { key: 'physio',  label: 'PhysioAI',   icon: '🏥', cls: 'physio', roles: ['admin', 'physio', 'coach'] },
  { key: 'nutri',   label: 'NutriAI',    icon: '🥗', cls: 'nutri', roles: ['admin', 'nutritionist', 'coach'] },
  { key: 'chat',    label: 'Chatbot',    icon: '💬', cls: 'chat', roles: ['all'] },
  { key: 'monitor', label: 'Monitoring', icon: '📊', cls: '', roles: ['admin'] },
];

function filterModules(modules, role) {
  if (!role) return modules;
  const userRole = role.toLowerCase();
  return modules.filter(m => m.roles.includes('all') || m.roles.includes(userRole) || userRole === 'admin');
}

function Overview({ setPage, userRole }) {
  const [counts, setCounts]         = useState({ players: '…', injuries: '…', foods: '…', contracts: '…' });
  const [summary, setSummary]       = useState(null);
  const [summaryErr, setSummaryErr] = useState(false);

  useEffect(() => {
    // KPI counts
    const get = d => Array.isArray(d.data) ? d.data.length : (d.data.count ?? d.data.results?.length ?? '?');
    Promise.all([
      axios.get('/api/scout/players/').catch(() => ({ data: { count: '🔒' } })),
      axios.get('/api/v2/physio/squad/daily-risk').catch(() => ({ data: { summary: { injured: '🔒' } } })),
      axios.get('/api/nutri/foods/').catch(() => ({ data: { count: '🔒' } })),
      axios.get('/api/scout/contracts/').catch(() => ({ data: { count: '🔒' } })),
    ]).then(([p, i, f, c]) => setCounts({
      players: get(p),
      injuries: i.data?.summary?.injured ?? '?',
      foods: get(f),
      contracts: get(c),
    })).catch(() => {});

    // Dashboard summary (real chart data)
    axios.get('/api/dashboard/summary/')
      .then(r => setSummary(r.data))
      .catch(() => setSummaryErr(true));
  }, []);

  const barData  = summary?.position_distribution || [];
  const pieData  = summary?.player_status_mix     || [];
  const lineData = summary?.monthly_injury_trend  || [];
  const topXg    = summary?.top_scorers_xg        || [];

  return (
    <div className="overview">
      <div style={{ marginBottom: '32px' }}>
        <h4 style={{ fontSize: '0.75rem', color: 'var(--neon-cyan)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px', fontWeight: '700' }}>Executive Snapshot</h4>
        <h2>Club Portfolio Intelligence</h2>
        <p className="subtitle">Real-time view of player composition, injury risks, and nutritional plans for faster management decisions.</p>
        {summaryErr && <p style={{ fontSize: '0.72rem', color: '#f59e0b', marginTop: 4 }}>⚠ Dashboard summary API unavailable.</p>}
      </div>

      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '32px' }}>
        {[
          ['Total Players',    counts.players,   'Active players in current dataset'],
          ['Active Contracts', counts.contracts, 'Player retention footprint'],
          ['Total Injuries',   counts.injuries,  'Historical injuries logged'],
          ['Food Items',       counts.foods,     'Nutritional coverage complexity'],
        ].map(([label, val, sub]) => (
          <div key={label} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '20px' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px', fontWeight: '700' }}>{label}</div>
            <div style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--text-primary)' }}>{val}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* Charts grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>

        {/* Position Distribution */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '24px' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '24px' }}>Position Distribution</h4>
          <div style={{ height: '250px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
                <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {barData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Player Status Mix */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '24px' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '24px' }}>Player Status Mix</h4>
          <div style={{ height: '210px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} innerRadius={60} outerRadius={90} paddingAngle={5} dataKey="value" stroke="none">
                    {pieData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>{summary ? 'All players fit — no recent injuries or high-RPE loads' : '…'}</p>
            )}
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '16px' }}>
            {pieData.map((e, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: e.fill }} />
                {e.name} ({e.value})
              </div>
            ))}
          </div>
        </div>

        {/* Monthly Injury Trend */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '24px' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '24px' }}>Monthly Injury Trend (last 12 months)</h4>
          <div style={{ height: '250px' }}>
            {lineData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={lineData}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--neon-pink)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--neon-pink)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px' }} />
                  <Area type="monotone" dataKey="value" stroke="var(--neon-pink)" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" name="Injuries" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>{summary ? 'No injuries in the past 12 months' : '…'}</p>
              </div>
            )}
          </div>
        </div>

        {/* Top Players by xG */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '24px' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '16px' }}>Top Players by xG</h4>
          {topXg.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '9px' }}>
              {topXg.map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '16px', fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'right' }}>{i + 1}</span>
                  <span style={{ flex: 1, fontSize: '0.82rem', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', minWidth: 30 }}>{p.position}</span>
                  <div style={{ width: '80px', height: '6px', background: 'var(--border-color)', borderRadius: '3px' }}>
                    <div style={{ height: '6px', width: Math.min(100, (p.xg_proxy / (topXg[0]?.xg_proxy || 1)) * 100) + '%', background: 'var(--neon-pink)', borderRadius: '3px' }} />
                  </div>
                  <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--neon-pink)', minWidth: 36, textAlign: 'right' }}>{p.xg_proxy}</span>
                </div>
              ))}
            </div>
          ) : (
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: 12 }}>No player stats yet — explore modules:</p>
              <div className="cards-grid" style={{ marginBottom: 0 }}>
                {filterModules(MODULES, userRole).filter(m => m.key === 'physio' || m.key === 'nutri').map(m => (
                  <div key={m.key} className={`card ${m.cls}`} onClick={() => setPage(m.key)} style={{ padding: '16px' }}>
                    <div className="card-icon" style={{ fontSize: '1.5rem', marginBottom: '8px' }}>{m.icon}</div>
                    <h3 style={{ fontSize: '0.9rem' }}>{m.label}</h3>
                    <p style={{ fontSize: '0.75rem' }}>{m.key === 'physio' ? 'Risk & training load' : 'Meal plans'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* API Endpoints */}
      <div className="api-list">
        <h3>Live API Endpoints</h3>
        <ul>
          {[
            ['GET',      '/api/dashboard/summary/'],
            ['GET/POST', '/api/scout/players/'],
            ['GET/POST', '/api/scout/contracts/'],
            ['GET',      '/api/v2/physio/squad/daily-risk'],
            ['POST',     '/api/v2/physio/simulator/assess'],
            ['POST',     '/api/v2/physio/absence/predict'],
            ['GET',      '/api/v2/physio/players/profiles'],
            ['GET/POST', '/api/nutri/foods/'],
            ['POST',     '/api/nutri/meal-calc/'],
            ['POST',     '/api/nutri/generate-plan/'],
            ['POST',     '/api/chat/'],
          ].map(([m, p]) => (
            <li key={p}>
              <span className="method">{m}</span>
              <span className="endpoint">{p}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState('home');
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    let mounted = true;
    restoreSession()
      .then((u) => {
        if (mounted) setUser(u);
      })
      .finally(() => {
        if (mounted) setAuthReady(true);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleLogin = (u) => setUser(u);

  const handleLogout = () => {
    logout();
    setUser(null);
    setPage('home');
  };

  if (!authReady) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', color: '#9ca3af' }}>
        Checking session...
      </div>
    );
  }

  if (!user) return <Login onLogin={handleLogin} />;

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>SmartClub</h1>
          <p>Club Intelligence</p>
        </div>
        <div className="nav-section">Modules</div>
        {filterModules(MODULES, user?.role).map(m => (
          <button
            key={m.key}
            className={`nav-item ${m.cls} ${page === m.key ? `active ${m.cls}` : ''}`}
            onClick={() => setPage(m.key)}
          >
            <span className="nav-icon">{m.icon}</span>
            {m.label}
          </button>
        ))}
        <div className="sidebar-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--neon-cyan), var(--neon-pink))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem', fontWeight: 'bold', color: '#0d0f15' }}>
              {(user?.full_name || user?.role || 'U')[0].toUpperCase()}
            </div>
            <div>
              <div style={{ color: 'var(--text-primary)', fontWeight: '600', fontSize: '0.8rem' }}>
                {user?.full_name || 'User'}
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'capitalize' }}>
                {user?.role || 'member'}
              </div>
            </div>
          </div>
          <button
            style={{ marginTop: '16px', width: '100%', padding: '8px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '0.8rem', transition: 'all 0.2s' }}
            onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
            onMouseOut={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
            onClick={handleLogout}
          >
            <span>→</span> Logout
          </button>
        </div>
      </aside>
      <main className="main-content">
        {page === 'home'    && <Overview setPage={setPage} userRole={user?.role} />}
        {page === 'physio'  && <PhysioAI />}
        {page === 'nutri'   && <NutriAI />}
        {page === 'chat'    && <Chatbot />}
        {page === 'monitor' && <MonitoringDashboard />}
      </main>
    </div>
  );
}
