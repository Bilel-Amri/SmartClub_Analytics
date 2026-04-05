/**
 * NutriAI — Professional Sports Nutrition Module
 * ================================================
 * Features:
 *  • Periodization Toggle (Recovery | Training | Match)
 *  • Macro Ring Chart — Target vs Actual (Recharts PieChart)
 *  • Training-Load sync: live carb adjustments from PhysioAI data
 *  • Recovery Nutrition Mode — activated by active Injury record
 *  • Common Sports Foods filter chips
 *  • Supplement Tracker with anti-doping (WADA/IOC) batch-test compliance
 *  • Live post-session dinner feedback (> 10 km → extra CHO)
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  Activity, AlertTriangle, CheckCircle, FlaskConical,
  Salad, ShieldCheck, Utensils, Zap,
} from 'lucide-react';

// ─── Palette ────────────────────────────────────────────────────────────────
const C = {
  carbs:   '#3b82f6',
  protein: '#ef4444',
  fat:     '#22c55e',
  cal:     '#f59e0b',
  bg:      '#0f172a',
  card:    '#111827',
  border:  '#1e293b',
  text:    '#f1f5f9',
  muted:   '#64748b',
};

const DAY_PERIOD = [
  { key: 'rest',     label: 'Recovery Day', icon: '🛌', color: '#22c55e' },
  { key: 'training', label: 'Training Day',  icon: '⚡', color: '#3b82f6' },
  { key: 'match',    label: 'Match Day',     icon: '🏆', color: '#ef4444' },
];
const GOALS    = ['maintain', 'bulk', 'cut'];
const GOAL_COLOR = { maintain: '#3b82f6', bulk: '#22c55e', cut: '#ef4444' };

// Common sports food spotlight categories (synced with backend SPORTS_FOOD_FILTERS)
const FOOD_CHIPS = [
  'Chicken', 'Pasta', 'Whey', 'Avocado', 'Rice',
  'Eggs', 'Oats', 'Salmon', 'Banana', 'Sweet Potato', 'Broccoli', 'Greek Yoghurt',
];

const MEAL_TIMES = [
  'breakfast', 'am_snack', 'lunch', 'pm_snack',
  'dinner', 'pre_train', 'post_train', 'pre_sleep',
];

// ─── Helper utils ────────────────────────────────────────────────────────────
const fmtDate   = d  => d ? new Date(d).toLocaleDateString() : '—';
const fmtNum    = (v, dec = 0) => v != null ? Number(v).toFixed(dec) : '—';
const showFlash_ = (setFlash, msg) => { setFlash(msg); setTimeout(() => setFlash(''), 3500); };

// ─────────────────────────────────────────────────────────────────────────────
// Shared atoms
// ─────────────────────────────────────────────────────────────────────────────

function Flash({ msg }) {
  if (!msg) return null;
  return (
    <div style={{ background: '#0f4', color: '#052', borderRadius: 6, padding: '8px 16px',
                  marginBottom: 10, fontSize: 13, fontWeight: 600 }}>{msg}</div>
  );
}

function MacroCard({ label, value, unit, color }) {
  return (
    <div className="macro-card" style={{ borderTop: `4px solid ${color}` }}>
      <div className="macro-val" style={{ color }}>{value != null ? fmtNum(value) : '—'}</div>
      <div className="macro-unit">{unit}</div>
      <div className="macro-label">{label}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Periodization Toggle
// ─────────────────────────────────────────────────────────────────────────────

function PeriodizationToggle({ value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {DAY_PERIOD.map(p => (
        <button
          key={p.key}
          type="button"
          onClick={() => onChange(p.key)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 16px', borderRadius: 8, cursor: 'pointer', fontWeight: 700,
            fontSize: 13, border: `2px solid ${value === p.key ? p.color : C.border}`,
            background: value === p.key ? p.color + '22' : 'transparent',
            color: value === p.key ? p.color : C.muted,
            transition: 'all 0.15s',
          }}
        >
          <span>{p.icon}</span> {p.label}
        </button>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Macro Ring Chart — Target vs Actual
// ─────────────────────────────────────────────────────────────────────────────

function MacroRingChart({ target, actual, title }) {
  if (!target) return null;

  const macros = [
    { name: 'Protein', tgt: target.protein_g, act: actual?.protein_g ?? 0, color: C.protein },
    { name: 'Carbs',   tgt: target.carbs_g,   act: actual?.carbs_g   ?? 0, color: C.carbs   },
    { name: 'Fat',     tgt: target.fat_g,     act: actual?.fat_g     ?? 0, color: C.fat     },
  ];

  const outerData = macros.map(m => ({ name: m.name + ' target', value: m.tgt, color: m.color, opacity: 0.35 }));
  const innerData = macros.map(m => ({ name: m.name + ' actual', value: m.act, color: m.color, opacity: 1.0  }));

  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: '14px 18px', marginTop: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {title || 'Macros — Target vs Actual'}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          {/* Outer ring = Target */}
          <Pie data={outerData} cx="50%" cy="50%" outerRadius={80} innerRadius={60} dataKey="value" strokeWidth={0}>
            {outerData.map((e, i) => <Cell key={i} fill={e.color} fillOpacity={e.opacity} />)}
          </Pie>
          {/* Inner ring = Actual */}
          <Pie data={innerData} cx="50%" cy="50%" outerRadius={55} innerRadius={35} dataKey="value" strokeWidth={0}>
            {innerData.map((e, i) => <Cell key={i} fill={e.color} fillOpacity={e.opacity} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: C.bg, border: 'none', borderRadius: 6, color: C.text, fontSize: 11 }}
            formatter={(v, n) => [`${Number(v).toFixed(1)} g`, n]}
          />
          <Legend wrapperStyle={{ color: C.muted, fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 4, flexWrap: 'wrap' }}>
        {macros.map(m => (
          <div key={m.name} style={{ textAlign: 'center', fontSize: 11 }}>
            <div style={{ color: m.color, fontWeight: 700 }}>{m.name}</div>
            <div style={{ color: C.muted }}>{fmtNum(m.act, 1)}g / {fmtNum(m.tgt, 1)}g</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Recovery Nutrition Banner
// ─────────────────────────────────────────────────────────────────────────────

function RecoveryBanner({ recovery }) {
  if (!recovery) return null;
  const [ open, setOpen ] = useState(false);
  return (
    <div style={{ background: '#1e1000', border: '1.5px solid #f59e0b', borderRadius: 10, padding: '12px 16px', marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        <Activity size={16} color="#f59e0b" />
        <span style={{ fontWeight: 700, color: '#f59e0b', fontSize: 13 }}>
          🏥 Recovery Nutrition Mode Active — {recovery.active_injury} ({recovery.severity})
        </span>
        <span style={{ marginLeft: 'auto', color: '#f59e0b', fontSize: 11 }}>{open ? '▲ hide' : '▼ details'}</span>
      </div>

      {open && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={{ fontSize: 12, color: '#fcd34d', margin: 0 }}>{recovery.focus}</p>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {[
              { label: 'Collagen', val: recovery.collagen_g_day + 'g/day' },
              { label: 'Zinc',     val: recovery.zinc_mg_day    + 'mg/day' },
              { label: 'Omega-3',  val: recovery.omega3_g_day   + 'g/day' },
              { label: 'Vit C',    val: recovery.vitamin_c_mg_day + 'mg/day' },
              ...(recovery.creatine_g_day ? [{ label: 'Creatine', val: recovery.creatine_g_day + 'g/day' }] : []),
            ].map(({ label, val }) => (
              <div key={label} style={{ background: '#2a1800', borderRadius: 6, padding: '6px 12px', textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase' }}>{label}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#fbbf24' }}>{val}</div>
              </div>
            ))}
          </div>

          {recovery.meal_timing && (
            <div style={{ background: '#1a1200', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 4, textTransform: 'uppercase' }}>Meal Timing</div>
              <p style={{ fontSize: 12, color: '#fcd34d', margin: 0 }}>{recovery.meal_timing}</p>
            </div>
          )}

          {recovery.anti_doping_note && (
            <div style={{ background: '#1a0a0a', border: '1px solid #7f1d1d', borderRadius: 6, padding: '8px 12px', display: 'flex', gap: 8 }}>
              <AlertTriangle size={14} color="#ef4444" style={{ flexShrink: 0, marginTop: 1 }} />
              <p style={{ fontSize: 11, color: '#fca5a5', margin: 0 }}>{recovery.anti_doping_note}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Live Feedback Banner (post-game dinner CHO)
// ─────────────────────────────────────────────────────────────────────────────

function LiveFeedbackBanner({ feedback }) {
  if (!feedback || !feedback.dinner_adjustment) return null;
  return (
    <div style={{ background: '#0d1f3b', border: '1.5px solid #3b82f6', borderRadius: 10, padding: '12px 16px', marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Zap size={16} color="#3b82f6" />
        <span style={{ fontWeight: 700, color: '#3b82f6', fontSize: 13 }}>Live Dinner Update — Extra CHO Required</span>
      </div>
      <p style={{ fontSize: 12, color: '#93c5fd', margin: '0 0 8px' }}>{feedback.note}</p>
      <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 6px' }}>{feedback.timing}</p>
      {feedback.recommended_foods && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {feedback.recommended_foods.map((f, i) => (
            <span key={i} style={{ background: '#1e3a5f', borderRadius: 4, padding: '3px 8px', fontSize: 11, color: '#93c5fd' }}>{f}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Training Load Context Banner
// ─────────────────────────────────────────────────────────────────────────────

function LoadBanner({ ctx }) {
  if (!ctx || ctx.load_band === 'insufficient_data') return null;
  const isHigh = ctx.above_80p_last_session;
  const isLow  = ctx.below_20p_last_session;
  if (!isHigh && !isLow) return null;

  return (
    <div style={{
      background: isHigh ? '#1a0d00' : '#0a1a0d',
      border: `1.5px solid ${isHigh ? '#f59e0b' : '#22c55e'}`,
      borderRadius: 8, padding: '8px 14px', marginBottom: 10,
      display: 'flex', alignItems: 'center', gap: 8,
    }}>
      <span style={{ fontSize: 16 }}>{isHigh ? '🔺' : '🔻'}</span>
      <span style={{ fontSize: 12, color: isHigh ? '#fcd34d' : '#86efac', fontWeight: 600 }}>
        {isHigh
          ? `High training load detected (>P80) → Carbohydrates set to ${ctx.carbs_g_per_kg?.toFixed(1)} g/kg`
          : `Low training load (<P20) → Carbohydrates reduced to ${ctx.carbs_g_per_kg?.toFixed(1)} g/kg`}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sports Food Filter Chips
// ─────────────────────────────────────────────────────────────────────────────

function FoodFilterChips({ active, onSelect }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
      <button
        type="button"
        onClick={() => onSelect('')}
        style={{
          padding: '4px 10px', borderRadius: 20, fontSize: 11, cursor: 'pointer',
          border: `1px solid ${!active ? '#3b82f6' : C.border}`,
          background: !active ? '#3b82f633' : 'transparent',
          color: !active ? '#93c5fd' : C.muted,
        }}
      >All</button>
      {FOOD_CHIPS.map(name => (
        <button
          key={name}
          type="button"
          onClick={() => onSelect(name === active ? '' : name)}
          style={{
            padding: '4px 10px', borderRadius: 20, fontSize: 11, cursor: 'pointer',
            border: `1px solid ${active === name ? '#3b82f6' : C.border}`,
            background: active === name ? '#3b82f633' : 'transparent',
            color: active === name ? '#93c5fd' : C.muted,
          }}
        >{name}</button>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Supplement anti-doping badge
// ─────────────────────────────────────────────────────────────────────────────

function CertBadge({ tested }) {
  return tested
    ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#052e1e', color: '#22c55e', borderRadius: 4, padding: '2px 7px', fontSize: 10, fontWeight: 700 }}><CheckCircle size={10} /> Certified</span>
    : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#2d0d0d', color: '#ef4444', borderRadius: 4, padding: '2px 7px', fontSize: 10, fontWeight: 700 }}><AlertTriangle size={10} /> UNCERTIFIED</span>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main NutriAI Component
// ─────────────────────────────────────────────────────────────────────────────

export default function NutriAI() {
  const [tab, setTab]       = useState('foods');
  const [players, setPlayers] = useState([]);
  const [loadingPlayers, setLoadingPlayers] = useState(true);
  const [playersLoadError, setPlayersLoadError] = useState('');
  const [foods, setFoods]   = useState([]);
  const [plans, setPlans]   = useState([]);
  const [flash, setFlash]   = useState('');
  const sf = msg => showFlash_(setFlash, msg);

  // ── Food database state ──────────────────────────────────────────────────
  const [fForm, setFForm]       = useState({ name: '', calories_100g: '', protein_100g: '', carbs_100g: '', fat_100g: '' });
  const [foodSearch, setFoodSearch] = useState('');
  const [foodChip, setFoodChip] = useState('');

  // ── Plan generation state ─────────────────────────────────────────────────
  const [planForm, setPlanForm] = useState({ player: '', date: '', day_type: 'training', goal: 'maintain', weight_kg: '', height_cm: '', age: '', sex: 'M' });
  const [planResult, setPlanResult]   = useState(null);
  const [planLoading, setPlanLoading] = useState(false);

  // ── Live feedback state ───────────────────────────────────────────────────
  const [fbPlayer, setFbPlayer]     = useState('');
  const [fbDist, setFbDist]         = useState('');
  const [fbResult, setFbResult]     = useState(null);

  // ── Meal calculator state ─────────────────────────────────────────────────
  const [mealItems, setMealItems] = useState([{ food_name: '', grams: '' }]);
  const [mealResult, setMealResult] = useState(null);
  const [mealPlanId, setMealPlanId] = useState('');
  const [mealTime, setMealTime]   = useState('breakfast');

  // ── Supplements state ─────────────────────────────────────────────────────
  const [supps, setSupps]       = useState([]);
  const [suppPlayer, setSuppPlayer] = useState('');
  const [suppWarn, setSuppWarn] = useState(null);
  const [suppForm, setSuppForm] = useState({
    player: '', date: '', name: '', dose_mg: '', timing: 'post_train',
    batch_tested: false, batch_number: '', cert_body: '', notes: '',
  });

  const normalizePlayers = useCallback((rows = []) => {
    const seen = new Set();
    const normalized = [];
    rows.forEach((p, idx) => {
      const id = p?.id ?? p?.player_id ?? p?.player ?? null;
      const fullName = (
        p?.full_name
        || p?.player_name
        || p?.name
        || [p?.first_name, p?.last_name].filter(Boolean).join(' ')
      )?.trim();
      if (id == null || !fullName) return;
      const key = String(id);
      if (seen.has(key)) return;
      seen.add(key);
      normalized.push({ ...p, id, full_name: fullName || `Player ${idx + 1}` });
    });
    return normalized;
  }, []);

  const toRows = useCallback((data) => {
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.results)) return data.results;
    if (Array.isArray(data?.players)) return data.players;
    return [];
  }, []);

  const toRelativeUrl = (nextUrl) => {
    if (!nextUrl) return null;
    const apiIdx = nextUrl.indexOf('/api/');
    return apiIdx >= 0 ? nextUrl.slice(apiIdx) : nextUrl;
  };

  const fetchScoutPlayers = useCallback(async () => {
    let url = '/api/scout/players/';
    let pageGuard = 0;
    const all = [];
    while (url && pageGuard < 20) {
      const r = await axios.get(url);
      all.push(...toRows(r.data));
      if (Array.isArray(r.data)) break;
      url = toRelativeUrl(r.data?.next);
      pageGuard += 1;
    }
    return normalizePlayers(all);
  }, [normalizePlayers, toRows]);

  const loadPlayers = useCallback(async () => {
    setLoadingPlayers(true);
    setPlayersLoadError('');
    try {
      let list = await fetchScoutPlayers();
      if (!list.length) {
        const fallback = await axios.get('/api/v2/physio/players/profiles').then(r => normalizePlayers(toRows(r.data))).catch(() => []);
        list = fallback;
      }
      setPlayers(list);
      if (!list.length) {
        setPlayersLoadError('No players found. Add players first.');
      }
    } catch {
      setPlayers([]);
      setPlayersLoadError('Could not load players. Ensure backend is running and your session is active.');
    } finally {
      setLoadingPlayers(false);
    }
  }, [fetchScoutPlayers, normalizePlayers, toRows]);

  // ─── Initial data load ────────────────────────────────────────────────────
  const refreshFoods = useCallback((q = '', cat = '') => {
    const params = {};
    if (q)   params.q        = q;
    if (cat) params.category = cat;
    axios.get('/api/nutri/foods/', { params }).then(r => setFoods(Array.isArray(r.data) ? r.data : (r.data.results || []))).catch(() => setFoods([]));
  }, []);

  const refreshPlans = useCallback(() =>
    axios.get('/api/nutri/plans/').then(r => setPlans(Array.isArray(r.data) ? r.data : (r.data.results || []))).catch(() => setPlans([])),
  []);

  useEffect(() => {
    loadPlayers();
    refreshFoods();
    refreshPlans();
  }, [loadPlayers, refreshFoods, refreshPlans]);

  const refreshSupps = useCallback((pid = '') => {
    const params = pid ? { player: pid } : {};
    axios.get('/api/nutri/supplements/', { params }).then(r => {
      setSupps(r.data.supplements || []);
      setSuppWarn(r.data.anti_doping_warning || null);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab === 'supplements') refreshSupps(suppPlayer);
  }, [tab, suppPlayer, refreshSupps]);

  // ─── Food chip filter ──────────────────────────────────────────────────────
  const handleChip = cat => {
    setFoodChip(cat);
    setFoodSearch('');
    refreshFoods('', cat);
  };

  const handleFoodSearch = q => {
    setFoodSearch(q);
    setFoodChip('');
    refreshFoods(q);
  };

  // ─── Add food ─────────────────────────────────────────────────────────────
  const addFood = async e => {
    e.preventDefault();
    try {
      await axios.post('/api/nutri/foods/', fForm);
      refreshFoods(foodSearch, foodChip);
      setFForm({ name: '', calories_100g: '', protein_100g: '', carbs_100g: '', fat_100g: '' });
      sf('Food added!');
    } catch { sf('Error adding food'); }
  };

  // ─── Generate plan ────────────────────────────────────────────────────────
  const generatePlan = async e => {
    e.preventDefault();
    setPlanLoading(true); setPlanResult(null);
    try {
      const res = await axios.post('/api/nutri/generate-plan/', planForm);
      setPlanResult(res.data);
      refreshPlans();
      sf('Plan generated!');
      // Auto-trigger live feedback if player set
      if (planForm.player) {
        const loads = await axios.get('/api/physio/training-loads/', { params: { player: planForm.player } }).catch(() => null);
        if (loads?.data?.length) {
          const latest = [...(Array.isArray(loads.data) ? loads.data : loads.data.results || [])].sort((a, b) => b.date.localeCompare(a.date))[0];
          if (latest?.total_distance_km) {
            const fb = await axios.post('/api/nutri/live-feedback/', { player_id: planForm.player, total_distance_km: latest.total_distance_km }).catch(() => null);
            if (fb) setPlanResult(prev => ({ ...prev, _live_feedback: fb.data }));
          }
        }
      }
    } catch { sf('Error generating plan'); }
    finally { setPlanLoading(false); }
  };

  // ─── Meal calculator ───────────────────────────────────────────────────────
  const calcMeal = async e => {
    e.preventDefault();
    const valid = mealItems.filter(i => i.food_name && i.grams);
    if (!valid.length) return;
    try {
      const res = await axios.post('/api/nutri/meal-calc/', { items: valid });
      setMealResult(res.data);

      // If a plan is selected, log the first item as a meal-log entry for ring chart
      if (mealPlanId && valid[0]) {
        const foodObj = foods.find(f => f.name.toLowerCase().includes(valid[0].food_name.toLowerCase()));
        if (foodObj) {
          await axios.post('/api/nutri/meal-logs/', {
            plan: Number(mealPlanId), food: foodObj.id,
            grams: Number(valid[0].grams), meal_time: mealTime,
          }).catch(() => {});
        }
      }
    } catch { sf('Meal calculation failed'); }
  };

  // ─── Live feedback manual ─────────────────────────────────────────────────
  const getliveFeedback = async e => {
    e.preventDefault();
    if (!fbPlayer || !fbDist) return;
    try {
      const res = await axios.post('/api/nutri/live-feedback/', { player_id: fbPlayer, total_distance_km: parseFloat(fbDist) });
      setFbResult(res.data);
    } catch { sf('Live feedback failed'); }
  };

  // ─── Add supplement ───────────────────────────────────────────────────────
  const addSupp = async e => {
    e.preventDefault();
    try {
      await axios.post('/api/nutri/supplements/', { ...suppForm, batch_tested: suppForm.batch_tested === true || suppForm.batch_tested === 'true' });
      refreshSupps(suppPlayer);
      setSuppForm({ player: '', date: '', name: '', dose_mg: '', timing: 'post_train', batch_tested: false, batch_number: '', cert_body: '', notes: '' });
      sf('Supplement logged!');
    } catch { sf('Error logging supplement'); }
  };

  // ─── Filtered foods ────────────────────────────────────────────────────────
  const filteredFoods = foods.filter(f =>
    (!foodSearch && !foodChip) ||
    (foodSearch && f.name.toLowerCase().includes(foodSearch.toLowerCase())) ||
    (foodChip   && f.name.toLowerCase().includes(foodChip.toLowerCase()))
  );

  const TABS = [
    ['foods',       '🥗 Foods',       foods.length],
    ['plans',       '📋 Plans',       plans.length],
    ['calc',        '🧮 Meal Calc',   null],
    ['supplements', '💊 Supplements', supps.length],
  ];

  return (
    <div className="module">
      <div className="module-header nutri-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Salad size={36} color="#22c55e" style={{ flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <h2 style={{ margin: 0 }}>NutriAI — Sports Nutrition</h2>
          <p style={{ margin: '2px 0 0', fontSize: 12, color: C.muted }}>
            Dynamic load-synced macros · Recovery adaptation · Anti-doping supplement log
          </p>
        </div>
      </div>

      <Flash msg={flash} />

      {(loadingPlayers || playersLoadError) && (
        <div style={{
          border: `1px solid ${playersLoadError ? '#7f1d1d' : C.border}`,
          background: playersLoadError ? '#1a0808' : '#0b1322',
          color: playersLoadError ? '#fca5a5' : '#93c5fd',
          borderRadius: 8,
          padding: '8px 12px',
          marginBottom: 10,
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}>
          <span>{loadingPlayers ? 'Loading players...' : playersLoadError}</span>
          {!loadingPlayers && (
            <button type="button" className="btn-secondary" style={{ fontSize: 11, padding: '4px 10px' }} onClick={loadPlayers}>
              Retry
            </button>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="tabs" style={{ flexWrap: 'wrap', marginBottom: 14 }}>
        {TABS.map(([k, l, cnt]) => (
          <button key={k} className={`tab ${tab === k ? 'active nutri-active' : ''}`} onClick={() => setTab(k)}>
            {l}{cnt != null ? ` (${cnt})` : ''}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          FOOD DATABASE
      ══════════════════════════════════════════════════════════════════════ */}
      {tab === 'foods' && (
        <>
          <div className="card-form">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Utensils size={15} color={C.muted} />
              <h3 style={{ margin: 0 }}>Add Food Item</h3>
            </div>
            <form className="form-row" onSubmit={addFood}>
              <input placeholder="Food name *" required value={fForm.name}
                onChange={e => setFForm(f => ({ ...f, name: e.target.value }))} />
              <input type="number" placeholder="Calories/100g" step="0.1" value={fForm.calories_100g}
                onChange={e => setFForm(f => ({ ...f, calories_100g: e.target.value }))} style={{ maxWidth: 120 }} />
              <input type="number" placeholder="Protein g" step="0.1" value={fForm.protein_100g}
                onChange={e => setFForm(f => ({ ...f, protein_100g: e.target.value }))} style={{ maxWidth: 100 }} />
              <input type="number" placeholder="Carbs g" step="0.1" value={fForm.carbs_100g}
                onChange={e => setFForm(f => ({ ...f, carbs_100g: e.target.value }))} style={{ maxWidth: 100 }} />
              <input type="number" placeholder="Fat g" step="0.1" value={fForm.fat_100g}
                onChange={e => setFForm(f => ({ ...f, fat_100g: e.target.value }))} style={{ maxWidth: 100 }} />
              <button type="submit" className="btn-primary">+ Add</button>
            </form>
          </div>

          {/* Search + sports food chips */}
          <div style={{ marginBottom: 10 }}>
            <input
              placeholder="🔍 Search foods…" value={foodSearch}
              onChange={e => handleFoodSearch(e.target.value)}
              style={{ width: '100%', maxWidth: 300, marginBottom: 8 }}
            />
            <FoodFilterChips active={foodChip} onSelect={handleChip} />
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Name</th><th>kcal/100g</th><th>Protein</th><th>Carbs</th><th>Fat</th><th>Source</th></tr>
              </thead>
              <tbody>
                {filteredFoods.length === 0 && <tr><td colSpan={6} className="empty">No foods found</td></tr>}
                {filteredFoods.map(f => (
                  <tr key={f.id}>
                    <td><strong>{f.name}</strong></td>
                    <td>{f.calories_100g}</td>
                    <td style={{ color: C.protein }}>{f.protein_100g}g</td>
                    <td style={{ color: C.carbs }}>{f.carbs_100g}g</td>
                    <td style={{ color: C.fat }}>{f.fat_100g}g</td>
                    <td><span className={`badge ${f.source === 'usda' ? 'moderate' : 'mild'}`}>{f.source}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          DAILY PLANS — full professional generate + ring chart
      ══════════════════════════════════════════════════════════════════════ */}
      {tab === 'plans' && (
        <div className="two-col">
          {/* Left: generate form */}
          <div style={{ flex: '1 1 0', minWidth: 0 }}>
            <div className="card-form">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <FlaskConical size={15} color={C.muted} />
                <h3 style={{ margin: 0 }}>Generate Nutrition Plan</h3>
              </div>
              <p style={{ fontSize: 11, color: C.muted, margin: '0 0 12px' }}>
                Mifflin-St Jeor BMR · Dynamic carbs from training load (P20/P80) · Injury adaptation
              </p>
              <form style={{ display: 'flex', flexDirection: 'column', gap: 10 }} onSubmit={generatePlan}>
                <div className="form-row">
                  <select required value={planForm.player} onChange={e => setPlanForm(f => ({ ...f, player: e.target.value }))} disabled={loadingPlayers || players.length === 0}>
                    <option value="">{loadingPlayers ? 'Loading players...' : (players.length ? 'Select player *' : 'No players available')}</option>
                    {players.map(p => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                  </select>
                  <input type="date" required value={planForm.date} onChange={e => setPlanForm(f => ({ ...f, date: e.target.value }))} />
                </div>

                {/* Periodization Toggle */}
                <div>
                  <div style={{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Training Period</div>
                  <PeriodizationToggle value={planForm.day_type} onChange={v => setPlanForm(f => ({ ...f, day_type: v }))} />
                </div>

                <div className="form-row">
                  {GOALS.map(g => (
                    <button key={g} type="button"
                      onClick={() => setPlanForm(f => ({ ...f, goal: g }))}
                      style={{
                        flex: 1, padding: '7px', borderRadius: 6, cursor: 'pointer', fontWeight: 700,
                        fontSize: 12, border: `2px solid ${planForm.goal === g ? GOAL_COLOR[g] : C.border}`,
                        background: planForm.goal === g ? GOAL_COLOR[g] + '22' : 'transparent',
                        color: planForm.goal === g ? GOAL_COLOR[g] : C.muted, textTransform: 'capitalize',
                      }}>{g}</button>
                  ))}
                  <select value={planForm.sex} onChange={e => setPlanForm(f => ({ ...f, sex: e.target.value }))} style={{ maxWidth: 80 }}>
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                  </select>
                </div>

                <div className="form-row">
                  <input type="number" placeholder="Weight kg *" required value={planForm.weight_kg}
                    onChange={e => setPlanForm(f => ({ ...f, weight_kg: e.target.value }))} style={{ maxWidth: 100 }} />
                  <input type="number" placeholder="Height cm *" required value={planForm.height_cm}
                    onChange={e => setPlanForm(f => ({ ...f, height_cm: e.target.value }))} style={{ maxWidth: 100 }} />
                  <input type="number" placeholder="Age *" required value={planForm.age}
                    onChange={e => setPlanForm(f => ({ ...f, age: e.target.value }))} style={{ maxWidth: 80 }} />
                </div>

                <button type="submit" className="btn-success" disabled={planLoading}>
                  {planLoading ? 'Calculating…' : '⚡ Generate Plan'}
                </button>
              </form>
            </div>

            {/* Result */}
            {planResult && (
              <div className="plan-card" style={{ marginTop: 12 }}>
                <h4 style={{ margin: '0 0 10px' }}>
                  {planResult.player_name} · {fmtDate(planResult.date)} ·{' '}
                  <span style={{ textTransform: 'capitalize', color: C.muted }}>{planResult.day_type}</span>
                </h4>

                {/* Load context banner */}
                <LoadBanner ctx={planResult.training_load_context} />

                {/* Recovery banner */}
                {planResult.recovery_mode_active && (
                  <RecoveryBanner recovery={planResult.recovery_nutrients} />
                )}

                {/* Live feedback banner */}
                <LiveFeedbackBanner feedback={planResult._live_feedback} />

                {/* Macro cards */}
                <div className="macro-grid">
                  <MacroCard label="Calories"  value={planResult.calories}   unit="kcal" color={C.cal}     />
                  <MacroCard label="Protein"   value={planResult.protein_g}  unit="g"    color={C.protein} />
                  <MacroCard label="Carbs"     value={planResult.carbs_g}    unit="g"    color={C.carbs}   />
                  <MacroCard label="Fat"       value={planResult.fat_g}      unit="g"    color={C.fat}     />
                </div>

                {/* g/kg breakdown */}
                {planResult.macros_per_kg && (
                  <div style={{ display: 'flex', gap: 10, marginTop: 8, flexWrap: 'wrap' }}>
                    {Object.entries(planResult.macros_per_kg).map(([k, v]) => (
                      <div key={k} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, padding: '4px 10px', fontSize: 11 }}>
                        <span style={{ color: C.muted }}>{k.replace('_g_per_kg', '').replace('_', ' ')} </span>
                        <strong style={{ color: C.text }}>{Number(v).toFixed(1)} g/kg</strong>
                      </div>
                    ))}
                  </div>
                )}

                {/* Ring chart skeleton (actual will populate once meal logs added) */}
                <MacroRingChart
                  target={{ protein_g: planResult.protein_g, carbs_g: planResult.carbs_g, fat_g: planResult.fat_g }}
                  actual={null}
                  title={`${DAY_PERIOD.find(d => d.key === planResult.day_type)?.icon || ''} ${planResult.day_type} — Macro Targets`}
                />

                {planResult.notes && (
                  <p style={{ fontSize: 11, color: '#475569', marginTop: 8 }}>{planResult.notes}</p>
                )}
              </div>
            )}
          </div>

          {/* Right: recent plans table */}
          <div style={{ flex: '1 1 0', minWidth: 0 }}>
            <h3 style={{ margin: '0 0 10px' }}>Recent Plans</h3>
            <div className="table-wrap" style={{ maxHeight: 500, overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr><th>Player</th><th>Date</th><th>Type</th><th>Goal</th><th>kcal</th><th>P</th><th>C</th><th>F</th></tr>
                </thead>
                <tbody>
                  {plans.length === 0 && <tr><td colSpan={8} className="empty">No plans yet</td></tr>}
                  {plans.map((p, i) => (
                    <tr key={i}>
                      <td><strong>{p.player_name}</strong></td>
                      <td style={{ fontSize: 11 }}>{fmtDate(p.date)}</td>
                      <td>
                        <span className={`badge ${p.day_type === 'match' ? 'severe' : p.day_type === 'training' ? 'moderate' : 'mild'}`}>
                          {DAY_PERIOD.find(d => d.key === p.day_type)?.icon} {p.day_type}
                        </span>
                      </td>
                      <td style={{ fontSize: 11, color: GOAL_COLOR[p.goal] || C.muted }}>{p.goal}</td>
                      <td style={{ fontWeight: 700 }}>{p.calories ? Math.round(p.calories) : '—'}</td>
                      <td style={{ color: C.protein }}>{p.protein_g ? Math.round(p.protein_g) : '—'}g</td>
                      <td style={{ color: C.carbs }}>{p.carbs_g   ? Math.round(p.carbs_g)   : '—'}g</td>
                      <td style={{ color: C.fat }}>{p.fat_g     ? Math.round(p.fat_g)     : '—'}g</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Live Feedback panel */}
            <div className="card-form" style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Zap size={14} color="#3b82f6" />
                <h4 style={{ margin: 0, fontSize: 13 }}>Live Post-Session Dinner Update</h4>
              </div>
              <p style={{ fontSize: 11, color: C.muted, margin: '0 0 8px' }}>
                Enter today's match/training distance → instantly recalculates dinner CHO
              </p>
              <form className="form-row" onSubmit={getliveFeedback}>
                <select value={fbPlayer} onChange={e => setFbPlayer(e.target.value)} required disabled={loadingPlayers || players.length === 0}>
                  <option value="">{loadingPlayers ? 'Loading players...' : (players.length ? 'Select player' : 'No players available')}</option>
                  {players.map(p => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
                <input type="number" step="0.1" placeholder="Distance km" value={fbDist}
                  onChange={e => setFbDist(e.target.value)} style={{ maxWidth: 110 }} required />
                <button type="submit" className="btn-primary" style={{ fontSize: 12 }}>Check</button>
              </form>
              {fbResult && <LiveFeedbackBanner feedback={fbResult} />}
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          MEAL CALCULATOR with Ring Chart (Target vs Actual)
      ══════════════════════════════════════════════════════════════════════ */}
      {tab === 'calc' && (
        <div style={{ maxWidth: 700 }}>
          <div className="card-form">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Activity size={15} color={C.muted} />
              <h3 style={{ margin: 0 }}>Meal Calculator</h3>
            </div>

            {/* Optional plan association for ring chart */}
            <div className="form-row" style={{ marginBottom: 8 }}>
              <select value={mealPlanId} onChange={e => setMealPlanId(e.target.value)} style={{ flex: 2 }}>
                <option value="">Link to plan (optional — enables ring chart)</option>
                {plans.map(p => <option key={p.id} value={p.id}>{p.player_name} · {fmtDate(p.date)} · {p.day_type}</option>)}
              </select>
              <select value={mealTime} onChange={e => setMealTime(e.target.value)}>
                {MEAL_TIMES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
              </select>
            </div>

            <form onSubmit={calcMeal}>
              {mealItems.map((item, idx) => (
                <div key={idx} className="form-row" style={{ marginBottom: 6 }}>
                  <select value={item.food_name}
                    onChange={e => setMealItems(prev => prev.map((it, i) => i === idx ? { ...it, food_name: e.target.value } : it))}
                    style={{ flex: 2 }}>
                    <option value="">Select food</option>
                    {foods.map(f => <option key={f.id} value={f.name}>{f.name}</option>)}
                  </select>
                  <input type="number" placeholder="Grams" value={item.grams} min="1" style={{ maxWidth: 90 }}
                    onChange={e => setMealItems(prev => prev.map((it, i) => i === idx ? { ...it, grams: e.target.value } : it))} />
                  {mealItems.length > 1 && (
                    <button type="button" className="btn-danger" style={{ padding: '6px 10px' }}
                      onClick={() => setMealItems(prev => prev.filter((_, i) => i !== idx))}>✕</button>
                  )}
                </div>
              ))}
              <div className="form-row" style={{ marginTop: 8 }}>
                <button type="button" className="btn-secondary"
                  onClick={() => setMealItems(prev => [...prev, { food_name: '', grams: '' }])}>+ Add food</button>
                <button type="submit" className="btn-primary">⚡ Calculate</button>
              </div>
            </form>
          </div>

          {mealResult && (
            <div className="plan-card" style={{ marginTop: 12 }}>
              <h4>Meal Totals</h4>
              <div className="macro-grid">
                <MacroCard label="Calories" value={mealResult.total_calories} unit="kcal" color={C.cal} />
                <MacroCard label="Protein"  value={mealResult.total_protein_g} unit="g"   color={C.protein} />
                <MacroCard label="Carbs"    value={mealResult.total_carbs_g}  unit="g"   color={C.carbs} />
                <MacroCard label="Fat"      value={mealResult.total_fat_g}    unit="g"   color={C.fat} />
              </div>

              {/* Ring Chart vs plan target */}
              {mealPlanId && (() => {
                const linkedPlan = plans.find(p => String(p.id) === String(mealPlanId));
                return linkedPlan ? (
                  <MacroRingChart
                    target={{ protein_g: linkedPlan.protein_g, carbs_g: linkedPlan.carbs_g, fat_g: linkedPlan.fat_g }}
                    actual={{ protein_g: mealResult.total_protein_g, carbs_g: mealResult.total_carbs_g, fat_g: mealResult.total_fat_g }}
                    title={`vs ${linkedPlan.day_type} target — ${linkedPlan.player_name}`}
                  />
                ) : null;
              })()}

              {mealResult.breakdown && (
                <div style={{ marginTop: 12 }}>
                  <h4 style={{ fontSize: 13, color: C.muted, marginBottom: 6 }}>Breakdown</h4>
                  <div className="table-wrap">
                    <table style={{ fontSize: 12 }}>
                      <thead><tr><th>Food</th><th>g</th><th>kcal</th><th>Protein</th><th>Carbs</th><th>Fat</th></tr></thead>
                      <tbody>
                        {mealResult.breakdown.map((b, i) => (
                          <tr key={i}>
                            <td>{b.food || b.food_name || '?'}</td>
                            <td>{b.grams}</td>
                            <td>{Number(b.calories).toFixed(0)}</td>
                            <td style={{ color: C.protein }}>{Number(b.protein_g).toFixed(1)}g</td>
                            <td style={{ color: C.carbs }}>{Number(b.carbs_g).toFixed(1)}g</td>
                            <td style={{ color: C.fat }}>{Number(b.fat_g).toFixed(1)}g</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          SUPPLEMENT TRACKER — Anti-doping compliance
      ══════════════════════════════════════════════════════════════════════ */}
      {tab === 'supplements' && (
        <>
          {/* Anti-doping warning */}
          {suppWarn && (
            <div style={{ background: '#1a0808', border: '1.5px solid #b91c1c', borderRadius: 10, padding: '10px 16px', marginBottom: 14, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <AlertTriangle size={16} color="#ef4444" style={{ flexShrink: 0, marginTop: 1 }} />
              <span style={{ fontSize: 12, color: '#fca5a5', fontWeight: 600 }}>{suppWarn}</span>
            </div>
          )}
          {!suppWarn && supps.length > 0 && (
            <div style={{ background: '#081a0d', border: '1.5px solid #166534', borderRadius: 10, padding: '10px 16px', marginBottom: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
              <ShieldCheck size={16} color="#22c55e" />
              <span style={{ fontSize: 12, color: '#86efac', fontWeight: 600 }}>All logged supplements are batch-tested certified. WADA/IOC compliant.</span>
            </div>
          )}

          <div className="two-col">
            {/* Form */}
            <div style={{ flex: '1 1 0', minWidth: 0 }}>
              <div className="card-form">
                <h3>Log Supplement</h3>
                <p style={{ fontSize: 11, color: C.muted, margin: '0 0 10px' }}>
                  All supplements must carry a batch-tested certification for WADA/IOC anti-doping audit compliance.
                </p>
                <form style={{ display: 'flex', flexDirection: 'column', gap: 8 }} onSubmit={addSupp}>
                  <div className="form-row">
                    <select required value={suppForm.player} onChange={e => setSuppForm(f => ({ ...f, player: e.target.value }))} disabled={loadingPlayers || players.length === 0}>
                      <option value="">{loadingPlayers ? 'Loading players...' : (players.length ? 'Player *' : 'No players available')}</option>
                      {players.map(p => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                    </select>
                    <input type="date" required value={suppForm.date} onChange={e => setSuppForm(f => ({ ...f, date: e.target.value }))} />
                  </div>
                  <div className="form-row">
                    <input placeholder="Product name *" required value={suppForm.name}
                      onChange={e => setSuppForm(f => ({ ...f, name: e.target.value }))} />
                    <input type="number" placeholder="Dose (mg)" required value={suppForm.dose_mg} step="0.1"
                      onChange={e => setSuppForm(f => ({ ...f, dose_mg: e.target.value }))} style={{ maxWidth: 100 }} />
                    <select value={suppForm.timing} onChange={e => setSuppForm(f => ({ ...f, timing: e.target.value }))}>
                      <option value="pre_train">Pre-Training</option>
                      <option value="intra_train">Intra-Training</option>
                      <option value="post_train">Post-Training</option>
                      <option value="morning">Morning</option>
                      <option value="evening">Evening</option>
                      <option value="with_meal">With Meal</option>
                    </select>
                  </div>

                  {/* Anti-doping fields */}
                  <div style={{ background: '#0d1a12', border: `1px solid ${C.border}`, borderRadius: 8, padding: '10px 12px' }}>
                    <div style={{ fontSize: 10, textTransform: 'uppercase', color: '#22c55e', fontWeight: 700, marginBottom: 8, letterSpacing: '0.06em' }}>
                      ⛉ Anti-Doping Compliance
                    </div>
                    <div className="form-row">
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: C.text, cursor: 'pointer' }}>
                        <input type="checkbox" checked={suppForm.batch_tested}
                          onChange={e => setSuppForm(f => ({ ...f, batch_tested: e.target.checked }))} />
                        Batch-tested certified
                      </label>
                    </div>
                    <div className="form-row" style={{ marginTop: 6 }}>
                      <input placeholder="Batch/Lot number" value={suppForm.batch_number}
                        onChange={e => setSuppForm(f => ({ ...f, batch_number: e.target.value }))} />
                      <input placeholder="Cert body (Informed Sport / BSCG / NSF)" value={suppForm.cert_body}
                        onChange={e => setSuppForm(f => ({ ...f, cert_body: e.target.value }))} />
                    </div>
                  </div>

                  <textarea placeholder="Notes" value={suppForm.notes} rows={2}
                    onChange={e => setSuppForm(f => ({ ...f, notes: e.target.value }))}
                    style={{ borderRadius: 6, border: `1px solid ${C.border}`, background: C.bg, color: C.text, padding: 8, fontSize: 12, resize: 'vertical' }} />
                  <button type="submit" className="btn-primary">+ Log Supplement</button>
                </form>
              </div>
            </div>

            {/* Table */}
            <div style={{ flex: '1 1 0', minWidth: 0 }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center' }}>
                <select value={suppPlayer} onChange={e => { setSuppPlayer(e.target.value); refreshSupps(e.target.value); }} style={{ maxWidth: 200 }} disabled={loadingPlayers || players.length === 0}>
                  <option value="">{loadingPlayers ? 'Loading players...' : (players.length ? 'All players' : 'No players available')}</option>
                  {players.map(p => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
                <span style={{ fontSize: 11, color: C.muted }}>{supps.length} supplements logged</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Player</th><th>Product</th><th>Dose</th><th>Timing</th><th>Cert.</th><th>Batch #</th><th>Date</th></tr>
                  </thead>
                  <tbody>
                    {supps.length === 0 && <tr><td colSpan={7} className="empty">No supplements logged</td></tr>}
                    {supps.map(s => (
                      <tr key={s.id} style={{ background: !s.batch_tested ? '#1a0808' : 'transparent' }}>
                        <td><strong>{s.player_name}</strong></td>
                        <td>{s.name}</td>
                        <td style={{ fontSize: 11 }}>{s.dose_mg}mg</td>
                        <td style={{ fontSize: 11, color: C.muted }}>{s.timing?.replace('_', ' ')}</td>
                        <td><CertBadge tested={s.batch_tested} /></td>
                        <td style={{ fontSize: 10, color: s.batch_number ? '#86efac' : '#475569' }}>
                          {s.batch_number || '—'}
                        </td>
                        <td style={{ fontSize: 11, color: C.muted }}>{fmtDate(s.date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

