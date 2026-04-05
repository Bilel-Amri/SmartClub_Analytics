import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const C = {
  bg: '#030b18',
  card: '#0b1730',
  card2: '#121d3a',
  border: '#1f335f',
  text: '#d9e8ff',
  muted: '#6f8fbd',
  high: '#ff3a6e',
  med: '#f4b322',
  low: '#1fe88f',
  cyan: '#00d4ff',
  violet: '#8c63ff',
};

function RiskPill({ band }) {
  const map = { high: C.high, medium: C.med, low: C.low };
  const c = map[band] || C.muted;
  return <span style={{ border: `1px solid ${c}`, color: c, borderRadius: 8, padding: '2px 10px', fontSize: 12, fontWeight: 700, textTransform: 'uppercase' }}>{band || 'unknown'}</span>;
}

function SectionCard({ children, title, right }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ color: C.cyan, fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase', fontSize: 13 }}>{title}</div>
        {right && <div style={{ marginLeft: 'auto' }}>{right}</div>}
      </div>
      {children}
    </div>
  );
}

function ExplainBox({ text, onExplain, loading }) {
  return (
    <div style={{ marginTop: 12 }}>
      <button onClick={onExplain} disabled={loading} style={{ width: '100%', background: 'transparent', color: C.text, border: `1px solid ${C.border}`, borderRadius: 10, padding: '10px 12px', fontWeight: 700, cursor: 'pointer' }}>
        {loading ? 'Generating AI explanation...' : '✦ Explain with AI'}
      </button>
      {text && <div style={{ marginTop: 8, border: `1px solid #7a5b1c`, borderRadius: 10, background: '#1a1e2a', color: '#9fc0f0', padding: 12, lineHeight: 1.55 }}>{text}</div>}
    </div>
  );
}

function TabButton({ active, n, label, onClick }) {
  return (
    <button onClick={onClick} style={{ flex: 1, background: active ? '#102246' : 'transparent', color: active ? C.text : C.muted, border: `1px solid ${C.border}`, borderRadius: 10, padding: '10px 12px', fontWeight: 800, textAlign: 'left', cursor: 'pointer' }}>
      <span style={{ display: 'inline-block', width: 18, height: 18, borderRadius: 100, textAlign: 'center', marginRight: 8, background: active ? C.cyan : '#2b3f6f', color: '#061a38', fontSize: 12, lineHeight: '18px' }}>{n}</span>
      {label}
    </button>
  );
}

function SquadDailyRiskTab() {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [aiText, setAiText] = useState({});
  const [aiLoading, setAiLoading] = useState({});

  const load = async () => {
    try {
      await axios.post('/api/v2/physio/similarity/seed').catch(() => {});
      const r = await axios.get('/api/v2/physio/squad/daily-risk');
      setData(r.data);
      const first = (r.data?.groups?.protect_today || [])[0];
      if (first) setExpanded({ [first.snapshot_id]: true });
    } catch {
      setData({ error: 'Failed to load daily risk data.' });
    }
  };

  useEffect(() => { load(); }, []);

  const explain = async (row) => {
    setAiLoading(s => ({ ...s, [row.snapshot_id]: true }));
    try {
      const r = await axios.post('/api/v2/physio/ai/explain', { function_type: 'squad_daily_risk', payload: row });
      setAiText(s => ({ ...s, [row.snapshot_id]: r.data.text }));
    } finally {
      setAiLoading(s => ({ ...s, [row.snapshot_id]: false }));
    }
  };

  const summary = data?.summary || {};
  const groups = data?.groups || {};

  const renderRow = (r) => {
    const open = !!expanded[r.snapshot_id];
    return (
      <div key={r.snapshot_id} style={{ border: `1px solid ${C.border}`, borderRadius: 12, marginBottom: 10, overflow: 'hidden', background: C.card2 }}>
        <div onClick={() => setExpanded(s => ({ ...s, [r.snapshot_id]: !s[r.snapshot_id] }))} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, cursor: 'pointer' }}>
          <div style={{ fontWeight: 800, color: C.text }}>{r.player_name}</div>
          <div style={{ color: C.muted, fontSize: 13 }}>{r.position} · {r.age}y</div>
          <div style={{ marginLeft: 'auto', fontSize: 34, fontWeight: 900, color: r.risk_band === 'high' ? C.high : r.risk_band === 'medium' ? C.med : C.low }}>{r.risk_score}</div>
          <RiskPill band={r.risk_band} />
        </div>
        {open && (
          <div style={{ borderTop: `1px solid ${C.border}`, padding: 12 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <SectionCard title="Risk drivers">
                <ul style={{ margin: 0, paddingLeft: 18, color: '#a8c4ea', lineHeight: 1.6 }}>
                  {(r.risk_drivers || []).map((d, i) => <li key={i}>{d}</li>)}
                </ul>
              </SectionCard>
              <SectionCard title="Training decision">
                <div style={{ color: '#a8c4ea', lineHeight: 1.8 }}>
                  <div>Load: {r.decision?.load}</div>
                  <div>Session: {r.decision?.session}</div>
                  <div>Monitor: {r.decision?.monitor}</div>
                  <div>Escalation: {r.decision?.escalation}</div>
                </div>
              </SectionCard>
            </div>
            <ExplainBox text={aiText[r.snapshot_id]} onExplain={() => explain(r)} loading={!!aiLoading[r.snapshot_id]} />
          </div>
        )}
      </div>
    );
  };

  if (!data) return <div style={{ color: C.muted }}>Loading squad risk...</div>;
  if (data.error) return <div style={{ color: C.high }}>{data.error}</div>;
  if (data.empty) return <div style={{ color: C.muted, padding: 40, textAlign: 'center', background: C.card, borderRadius: 14, border: `1px solid ${C.border}` }}>{data.message || 'No squad data available yet. Add players or sync data.'}</div>;

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(120px,1fr))', gap: 10, marginBottom: 14 }}>
        <SectionCard title="Protect today"><div style={{ color: C.high, fontSize: 38, fontWeight: 900 }}>{summary.protect_today || 0}</div></SectionCard>
        <SectionCard title="Monitor closely"><div style={{ color: C.med, fontSize: 38, fontWeight: 900 }}>{summary.monitor_closely || 0}</div></SectionCard>
        <SectionCard title="Ready to train"><div style={{ color: C.low, fontSize: 38, fontWeight: 900 }}>{summary.ready_to_train || 0}</div></SectionCard>
        <SectionCard title="Injured"><div style={{ color: '#7fb0e4', fontSize: 38, fontWeight: 900 }}>{summary.injured || 0}</div></SectionCard>
      </div>

      <SectionCard title="Protect today" right={<RiskPill band="high" />}>
        {(groups.protect_today || []).map(renderRow)}
      </SectionCard>
      <div style={{ height: 10 }} />
      <SectionCard title="Monitor closely" right={<RiskPill band="medium" />}>
        {(groups.monitor_closely || []).map(renderRow)}
      </SectionCard>
      <div style={{ height: 10 }} />
      <SectionCard title="Ready to train" right={<RiskPill band="low" />}>
        {(groups.ready_to_train || []).map(renderRow)}
      </SectionCard>
    </div>
  );
}

function PlayerRiskSimulatorTab() {
  const [mode, setMode] = useState('manual');
  const [players, setPlayers] = useState([]);
  const [loadingPlayers, setLoadingPlayers] = useState(true);
  
  const [form, setForm] = useState({ 
    player_name: '', age: 25, position: 'Midfielder', previous_injuries: 0, 
    injuries_last_2_seasons: 0, primary_zone: 'Hamstring', training_load_band: 'medium', 
    days_since_last_intense: 2, recurrence_same_zone: false,
    sleep_duration_value: 8, fatigue_value: 2, stress_value: 2, weekly_load_value: 1500
  });
  
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiText, setAiText] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    axios.get('/api/v2/physio/players/profiles').then(r => {
      setPlayers(r.data);
      if (r.data.length > 0) {
        setForm(f => ({ ...f, ...r.data[0] }));
      } else {
        setMode('manual');
      }
      setLoadingPlayers(false);
    }).catch(() => {
      setLoadingPlayers(false);
      setMode('manual');
    });
  }, []);

  const handleMode = (m) => {
    setMode(m);
    if (m === 'existing' && players.length > 0) {
      setForm(f => ({ ...f, ...players[0] }));
    }
    if (m === 'manual') {
      setForm({ player_name: '', age: 25, position: 'Midfielder', previous_injuries: 0, injuries_last_2_seasons: 0, primary_zone: 'Hamstring', training_load_band: 'medium', days_since_last_intense: 5, recurrence_same_zone: false, sleep_duration_value: 8, fatigue_value: 5, stress_value: 5, weekly_load_value: 1500 });
    }
    setResult(null);
    setAiText('');
  };

  const handlePlayerChange = (id) => {
    const p = players.find(x => x.id === parseInt(id));
    if (p) setForm(f => ({ ...f, ...p }));
    setResult(null);
    setAiText('');
  };

  const assess = async () => {
    setLoading(true);
    setResult(null);
    setAiText('');
    try {
      const r = await axios.post('/api/v2/physio/simulator/assess', form);
      setResult(r.data);
    } catch {
      setResult({ error: "Assessment failed. Ensure proper data and that the server is running." });
    } finally {
      setLoading(false);
    }
  };

  const explain = async () => {
    if (!result) return;
    setAiLoading(true);
    try {
      const r = await axios.post('/api/v2/physio/ai/explain', { function_type: 'player_risk_simulator', run_id: result.run_id, payload: { ...form, result } });
      setAiText(r.data.text);
    } catch {
      setAiText("Failed to load explanation.");
    } finally {
      setAiLoading(false);
    }
  };

  const color = useMemo(() => {
    if (!result) return C.muted;
    if (result.risk_band === 'high') return C.high;
    if (result.risk_band === 'medium') return C.med;
    return C.low;
  }, [result]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: 24 }}>
      <SectionCard title="Player profile">
        <div style={{ display: 'flex', gap: 5, marginBottom: 20 }}>
          <button onClick={() => handleMode('existing')} style={{ flex: 1, padding: '10px 12px', fontSize: 13, background: mode === 'existing' ? '#102246' : 'transparent', color: mode === 'existing' ? C.text : C.muted, borderRadius: 8, border: `1px solid ${mode === 'existing' ? C.cyan : C.border}`, cursor: 'pointer', fontWeight: 'bold' }}>Use existing player</button>
          <button onClick={() => handleMode('manual')} style={{ flex: 1, padding: '10px 12px', fontSize: 13, background: mode === 'manual' ? '#102246' : 'transparent', color: mode === 'manual' ? C.text : C.muted, borderRadius: 8, border: `1px solid ${mode === 'manual' ? C.cyan : C.border}`, cursor: 'pointer', fontWeight: 'bold' }}>Enter new player</button>
        </div>

        {mode === 'existing' && !loadingPlayers && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ color: '#88a0c4', fontSize: 13, marginBottom: 8, fontWeight: 600 }}>Select Player</div>
            <select value={form.id || ''} onChange={e => handlePlayerChange(e.target.value)} style={{ width: '100%', background: '#121e33', border: `1px solid ${C.border}`, borderRadius: 10, color: '#ffffff', padding: '12px 14px', fontSize: 14, outline: 'none', cursor: 'pointer' }}>
              {players.length === 0 && <option value="">No players found</option>}
              {players.map(p => <option key={p.id} value={p.id}>{p.player_name}</option>)}
            </select>
          </div>
        )}

        {(mode === 'manual' || mode === 'existing') && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', rowGap: 20, columnGap: 16, marginTop: 10 }}>
            {[
              ...(mode === 'manual' ? [['Player name', 'player_name', 'text']] : []),
              ['Age', 'age', 'number'],
              ['Position', 'position', ['Goalkeeper', 'Centre-back', 'Full-back', 'Midfielder', 'Winger', 'Forward', 'Striker']],
              ['Total previous injuries', 'previous_injuries', 'number'],
              ['Injuries — last 2 seasons', 'injuries_last_2_seasons', 'number'],
              ['Primary injury zone', 'primary_zone', ['Hamstring', 'Groin', 'Knee', 'Ankle', 'Calf', 'Back', 'Thigh', 'Other']],
              ['Training load this week', 'training_load_band', ['low', 'medium', 'high']],
              ['Days since last intense session', 'days_since_last_intense', 'number'],
              ['Sleep Hours', 'sleep_duration_value', 'number'],
              ['Fatigue (0-10)', 'fatigue_value', 'number'],
              ['Stress (0-10)', 'stress_value', 'number'],
              ['Weekly Load', 'weekly_load_value', 'number'],
            ].map(([label, key, type]) => (
              <div key={key} style={key === 'player_name' || key === 'primary_zone' || key === 'position' || key === 'training_load_band' ? { gridColumn: 'span 2' } : {}}>
                <div style={{ color: '#88a0c4', fontSize: 13, marginBottom: 8, fontWeight: 600 }}>{label}</div>
                {Array.isArray(type) ? (
                  <select value={form[key]} onChange={e => setForm(s => ({ ...s, [key]: e.target.value }))} style={{ width: '100%', background: '#121e33', border: `1px solid ${C.border}`, borderRadius: 10, color: '#ffffff', padding: '12px 14px', fontSize: 14, outline: 'none', cursor: 'pointer', appearance: 'auto' }}>
                    <option value="">Select...</option>
                    {type.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                  </select>
                ) : (
                  <input type={type} value={form[key]} onChange={e => setForm(s => ({ ...s, [key]: type === 'number' ? Number(e.target.value) : e.target.value }))} style={{ width: '100%', background: '#121e33', border: `1px solid ${C.border}`, borderRadius: 10, color: '#ffffff', padding: '12px 14px', fontSize: 14, outline: 'none', boxSizing: 'border-box' }} />
                )}
              </div>
            ))}
          </div>
        )}
        <button onClick={assess} disabled={loading} style={{ width: '100%', marginTop: 28, background: '#1d3b66', color: '#ffffff', border: 'none', borderRadius: 10, padding: 16, fontSize: 15, fontWeight: 800, cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
          {loading ? 'Assessing...' : 'Assess injury risk'}
        </button>
      </SectionCard>

      <div>
        <SectionCard title="Risk output">
          {!result && <div style={{ color: C.muted }}>Run an assessment to display score, key drivers, and similar profiles.</div>}
          {result && result.error && (
            <div style={{ background: '#2d1f1f', border: '1px solid #ff4a4a', borderRadius: 8, padding: 16 }}>
              <div style={{ color: '#ff8a8a', fontWeight: 'bold' }}>Assessment Error</div>
              <div style={{ color: '#ffffff', fontSize: 14, marginTop: 8 }}>{result.error}</div>
            </div>
          )}
          {result && !result.error && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 90, height: 90, borderRadius: 100, border: `3px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, fontSize: 40, color }}>{result.risk_score}</div>
                <div>
                  <div style={{ color, fontSize: 34, fontWeight: 900, textTransform: 'uppercase' }}>{result.risk_band} risk</div>
                  <div style={{ color: C.muted }}>Score {result.risk_score}/100</div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
                <SectionCard title="Key risk drivers">
                  <ul style={{ margin: 0, paddingLeft: 18, color: '#a8c4ea', lineHeight: 1.7 }}>
                    {(result.risk_drivers || []).map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </SectionCard>
                <SectionCard title="Training decision">
                  <ul style={{ margin: 0, paddingLeft: 18, color: '#a8c4ea', lineHeight: 1.7 }}>
                    {(result.decision?.training_decision || []).map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </SectionCard>
              </div>

              <SectionCard title="Similar historical profiles" right={<div style={{ color: C.violet, fontWeight: 800 }}>{(result.similar_profiles || []).length} found</div>}>
                {(result.similar_profiles || []).map((p, i) => (
                  <div key={i} style={{ border: `1px solid ${C.border}`, borderRadius: 10, padding: 10, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ color: C.text, fontWeight: 700, flex: 1 }}>{p.summary}</div>
                    <div style={{ color: C.high, fontWeight: 900 }}>{p.match_pct}%</div>
                  </div>
                ))}
              </SectionCard>

              <ExplainBox text={aiText} onExplain={explain} loading={aiLoading} />
            </>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

function AbsencePredictionTab() {
  const [mode, setMode] = useState('manual');
  const [players, setPlayers] = useState([]);
  const [loadingPlayers, setLoadingPlayers] = useState(true);

  const [form, setForm] = useState({ 
    player_name: '', age: 25, position: 'Striker', injury_type: 'Hamstring', 
    context: 'training session', previous_same_zone: 0, recurrence_same_zone: false, 
    training_load_band: 'high' 
  });
  
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiText, setAiText] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    axios.get('/api/v2/physio/players/profiles').then(r => {
      setPlayers(r.data);
      if (r.data.length > 0) {
        setForm(f => ({ ...f, player_name: r.data[0].player_name, age: r.data[0].age, position: r.data[0].position, id: r.data[0].id }));
      } else {
        setMode('manual');
      }
      setLoadingPlayers(false);
    }).catch(() => {
      setLoadingPlayers(false);
      setMode('manual');
    });
  }, []);

  const handleMode = (m) => {
    setMode(m);
    if (m === 'existing' && players.length > 0) {
      setForm(f => ({...f, player_name: players[0].player_name, age: players[0].age, position: players[0].position, id: players[0].id}));
    }
    if (m === 'manual') setForm(f => ({ ...f, player_name: '', age: 25, position: 'Striker', id: null }));
    setResult(null);
    setAiText('');
  };

  const handlePlayerChange = (id) => {
    const p = players.find(x => x.id === parseInt(id));
    if (p) setForm(f => ({...f, player_name: p.player_name, age: p.age, position: p.position, id: p.id}));
    setResult(null);
    setAiText('');
  };

  const predict = async () => {
    setLoading(true);
    setResult(null);
    setAiText('');
    try {
      const r = await axios.post('/api/v2/physio/absence/predict', form);
      const data = r.data;
      
      // Formatting bucket strings for frontend polish here so backend logic remains clean
      if (data.severity_bucket) {
        let label = data.severity_bucket;
        if (data.severity_bucket === '0_7') label = 'Very short absence · 0–7 days';
        else if (data.severity_bucket === '8_21') label = 'Short absence · 8–21 days';
        else if (data.severity_bucket === '22_42') label = 'Medium absence · 22–42 days';
        else if (data.severity_bucket === '43_plus') label = 'Long absence · 43+ days';
        data.formatted_bucket_display = label;
      }
      
      setResult(data);
    } catch {
      setResult({ error: "Prediction failed. Ensure the server is running." });
    } finally {
      setLoading(false);
    }
  };

  const explain = async () => {
    if (!result) return;
    setAiLoading(true);
    try {
      const r = await axios.post('/api/v2/physio/ai/explain', { function_type: 'absence_prediction', run_id: result.run_id, payload: { ...form, result } });
      setAiText(r.data.text);
    } catch {
       setAiText('Failed to load explanation.');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: 24 }}>
      <SectionCard title="Injury event">
        <div style={{ display: 'flex', gap: 5, marginBottom: 20 }}>
          <button onClick={() => handleMode('existing')} style={{ flex: 1, padding: '10px 12px', fontSize: 13, background: mode === 'existing' ? '#102246' : 'transparent', color: mode === 'existing' ? C.text : C.muted, borderRadius: 8, border: `1px solid ${mode === 'existing' ? C.cyan : C.border}`, cursor: 'pointer', fontWeight: 'bold' }}>Use existing player</button>
          <button onClick={() => handleMode('manual')} style={{ flex: 1, padding: '10px 12px', fontSize: 13, background: mode === 'manual' ? '#102246' : 'transparent', color: mode === 'manual' ? C.text : C.muted, borderRadius: 8, border: `1px solid ${mode === 'manual' ? C.cyan : C.border}`, cursor: 'pointer', fontWeight: 'bold' }}>Enter new player</button>
        </div>

        {mode === 'existing' && !loadingPlayers && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ color: '#88a0c4', fontSize: 13, marginBottom: 8, fontWeight: 600 }}>Select Player</div>
            {players.length === 0 ? (
              <div style={{ background: '#2d1f1f', color: '#ff8a8a', padding: '10px 14px', borderRadius: 8, fontSize: 13, border: '1px solid #4a2424', lineHeight: 1.4 }}>
                <span style={{ fontWeight: 800, display: 'block', marginBottom: 2 }}>No squad players available.</span>
                <span>Switch to "Enter new player" or sync squad data.</span>
              </div>
            ) : (
              <select value={form.id || ''} onChange={e => handlePlayerChange(e.target.value)} style={{ width: '100%', background: '#121e33', border: `1px solid ${C.border}`, borderRadius: 10, color: '#ffffff', padding: '12px 14px', fontSize: 14, outline: 'none', cursor: 'pointer' }}>
                <option value="" disabled>Select from squad...</option>
                {players.map(p => <option key={p.id} value={p.id}>{p.player_name}</option>)}
              </select>
            )}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', rowGap: 20, columnGap: 16, marginTop: 10 }}>
          {[
            ...(mode === 'manual' ? [['Player', 'player_name', 'text']] : []),
            ['Age', 'age', 'number'],
            ['Position', 'position', ['Goalkeeper', 'Defender', 'Midfielder', 'Forward', 'Striker']],
            ['Injury type', 'injury_type', ['Hamstring / Muscle', 'Knee Ligament', 'Ankle / Foot', 'Impact / Contusion', 'Illness / Virus', 'Groin', 'Back', 'Other']],
            ['Context', 'context', ['training session', 'match', 'warm-up', 'conditioning', 'off-pitch']],
            ['Prev injuries (same zone)', 'previous_same_zone', 'number'],
            ['Training load', 'training_load_band', ['low', 'medium', 'high']],
          ].map(([label, key, type]) => (
            <div key={key} style={key === 'player_name' || key === 'context' || key === 'injury_type' ? { gridColumn: 'span 2' } : {}}>
              <div style={{ color: '#88a0c4', fontSize: 13, marginBottom: 8, fontWeight: 600 }}>{label}</div>
              {Array.isArray(type) ? (
                <select 
                  value={form[key]} 
                  onChange={e => setForm(s => ({ ...s, [key]: e.target.value }))} 
                  style={{ width: '100%', background: '#121e33', border: `1px solid ${C.border}`, borderRadius: 10, color: '#ffffff', padding: '12px 14px', fontSize: 14, outline: 'none', cursor: 'pointer', appearance: 'auto' }}
                >
                  <option value="" disabled>Select...</option>
                  {type.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              ) : (
                <input 
                  type={type} 
                  value={form[key]} 
                  onChange={e => setForm(s => ({ ...s, [key]: type === 'number' ? Number(e.target.value) : e.target.value }))} 
                  style={{ width: '100%', background: '#121e33', border: `1px solid ${C.border}`, borderRadius: 10, color: '#ffffff', padding: '12px 14px', fontSize: 14, outline: 'none', boxSizing: 'border-box' }} 
                />
              )}
            </div>
          ))}
        </div>
        <label style={{ color: '#88a0c4', fontSize: 13, display: 'block', marginBottom: 10, marginTop: 15, fontWeight: 600, cursor: 'pointer' }}>
          <input type="checkbox" checked={form.recurrence_same_zone} onChange={e => setForm(s => ({ ...s, recurrence_same_zone: e.target.checked }))} style={{ marginRight: 8 }} /> Recurrence in same zone
        </label>
        <button onClick={predict} disabled={loading} style={{ width: '100%', marginTop: 20, background: '#1d3b66', color: '#ffffff', border: 'none', borderRadius: 10, padding: 16, fontSize: 15, fontWeight: 800, cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
          {loading ? 'Predicting...' : 'Predict & match'}
        </button>
      </SectionCard>

      <SectionCard title="ABSENCE PREDICTION">
        {!result && <div style={{ color: C.muted }}>Submit an injury event to estimate predicted absence days and historical matches.</div>}
        {result && result.error && (
          <div style={{ background: '#2d1f1f', borderRadius: 8, padding: 16, border: `1px solid #4a2424`, marginBottom: 16 }}>
            <div style={{ color: '#ff8a8a', fontSize: 13, textTransform: 'uppercase', fontWeight: 700 }}>Prediction Error</div>
            <div style={{ color: '#ffffff', fontSize: 14, marginTop: 8 }}>{result.error}</div>
          </div>
        )}
        {result && !result.error && (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
              {result.predicted_days !== undefined ? (
                <>
                  <div style={{ background: C.card2, borderRadius: 8, padding: 16, border: `1px solid ${C.border}` }}>
                    <div style={{ color: C.muted, fontSize: 13, textTransform: 'uppercase', marginBottom: 4, fontWeight: 700 }}>Predicted Absence</div>
                    <div style={{ color: C.high, fontWeight: 900, fontSize: 36 }}>{result.predicted_days} days</div>
                  </div>
                  <div style={{ background: '#122744', borderRadius: 8, padding: 12, border: `1px solid #1e3a5f`, display: 'inline-block', alignSelf: 'flex-start' }}>
                    <div style={{ color: '#a8c4ea', fontSize: 11, textTransform: 'uppercase', marginBottom: 2 }}>Severity Range</div>
                    <div style={{ color: '#ffffff', fontWeight: 800, fontSize: 16 }}>{result.formatted_bucket_display || result.severity_bucket}</div>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ background: C.card2, borderRadius: 8, padding: 16, border: `1px solid ${C.border}` }}>
                    <div style={{ color: C.muted, fontSize: 13, textTransform: 'uppercase', marginBottom: 4, fontWeight: 700 }}>Absence Range Estimate</div>
                    <div style={{ color: C.high, fontWeight: 900, fontSize: 36 }}>{result.absence_prediction.days_min}-{result.absence_prediction.days_max} days</div>
                    <div style={{ color: '#ffb86c', fontSize: 12, marginTop: 4 }}>Fallback absence range estimate used.</div>
                  </div>
                </>
              )}
            </div>
            <div style={{ color: C.muted, fontSize: 11, fontStyle: 'italic', marginBottom: 16 }}>
              Decision-support estimate, not a medical diagnosis.
            </div>

            <SectionCard title="Immediate Actions">
              <div style={{ color: '#a8c4ea', lineHeight: 1.8 }}>
                <div>Participation: {result.immediate_actions.participation}</div>
                <div>Medical: {result.immediate_actions.medical}</div>
                <div>Coach: {result.immediate_actions.coach_notification}</div>
                <div>Escalation: {result.immediate_actions.escalation}</div>
              </div>
            </SectionCard>

            <SectionCard title="Similar Historical Cases" right={<div style={{ color: C.violet, fontWeight: 800 }}>{result.historical_case_matching.count} similar</div>}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginBottom: 10 }}>
                <div style={{ background: C.card2, borderRadius: 8, padding: 8, textAlign: 'center' }}><div style={{ color: C.violet, fontSize: 30, fontWeight: 900 }}>{result.historical_case_matching.average_days}</div><div style={{ color: C.muted, fontSize: 12 }}>Average</div></div>
                <div style={{ background: C.card2, borderRadius: 8, padding: 8, textAlign: 'center' }}><div style={{ color: C.violet, fontSize: 30, fontWeight: 900 }}>{result.historical_case_matching.median_days}</div><div style={{ color: C.muted, fontSize: 12 }}>Median</div></div>
                <div style={{ background: C.card2, borderRadius: 8, padding: 8, textAlign: 'center' }}><div style={{ color: C.violet, fontSize: 30, fontWeight: 900 }}>{result.historical_case_matching.shortest_days}</div><div style={{ color: C.muted, fontSize: 12 }}>Shortest</div></div>
                <div style={{ background: C.card2, borderRadius: 8, padding: 8, textAlign: 'center' }}><div style={{ color: C.violet, fontSize: 30, fontWeight: 900 }}>{result.historical_case_matching.longest_days}</div><div style={{ color: C.muted, fontSize: 12 }}>Longest</div></div>
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, color: '#a8c4ea', lineHeight: 1.7 }}>
                {(result.historical_case_matching.cases || []).map((c, i) => <li key={i}>{c.profile?.player_name || c.player_name || 'Unknown'} &mdash; {c.absence_days || c.days} days ({(c.match_pct || c.similarity_score || 0).toString().split('.')[0]}% match)</li>)}
              </ul>
            </SectionCard>

            <SectionCard title="Explanation">
              <div style={{ color: C.muted, fontSize: 13, textTransform: 'uppercase', marginBottom: 8, fontWeight: 700 }}>
                Why this estimate?
              </div>
              <ExplainBox text={aiText} onExplain={explain} loading={aiLoading} />
            </SectionCard>
          </>
        )}
      </SectionCard>
    </div>
  );
}

export default function PhysioAIv2() {
  const [tab, setTab] = useState(1);
  return (
    <div style={{ background: C.bg, minHeight: '100vh', display: 'flex', justifyContent: 'center', padding: 40, fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ width: '100%', maxWidth: 1000 }}>
        <h1 style={{ color: '#fff', fontSize: 28, margin: '0 0 4px 0', letterSpacing: '-0.02em' }}>Physio AI</h1>
        <p style={{ color: '#88a0c4', fontSize: 15, margin: '0 0 24px 0' }}>Advanced clinical decision-support system for injury risk assessment and return-to-play forecasting.</p>

        <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
          <TabButton n="1" label="Squad daily risk" active={tab === 1} onClick={() => setTab(1)} />
          <TabButton n="2" label="Player risk simulator" active={tab === 2} onClick={() => setTab(2)} />
          <TabButton n="3" label="Absence predictor" active={tab === 3} onClick={() => setTab(3)} />
        </div>

        {tab === 1 && <SquadDailyRiskTab />}
        {tab === 2 && <PlayerRiskSimulatorTab />}
        {tab === 3 && <AbsencePredictionTab />}
      </div>
    </div>
  );
}
