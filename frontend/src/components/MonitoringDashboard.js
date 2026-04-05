/**
 * MonitoringDashboard.js
 * ──────────────────────
 * Grafana-style ML API monitoring panel.
 * Polls  GET /api/monitoring/metrics/  every 15 s.
 * Uses Recharts (already in the project).
 */

import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import {
  LineChart, Line,
  AreaChart, Area,
  BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';

// ── palette ──────────────────────────────────────────────────────────────
const C = {
  bg:        '#111216',
  panel:     '#1a1d27',
  panelBdr:  'rgba(255,255,255,0.06)',
  section:   '#0d0f15',
  sectionBdr:'rgba(255,255,255,0.08)',
  grid:      'rgba(255,255,255,0.06)',
  axis:      'rgba(255,255,255,0.35)',
  green:     '#73BF69',
  yellow:    '#FADE2A',
  orange:    '#FF9830',
  red:       '#F2495C',
  blue:      '#5794F2',
  purple:    '#B877D9',
  cyan:      '#37D9C0',
  pink:      '#F25295',
};

const EP_COLORS = [C.blue, C.green, C.orange, C.yellow, C.red, C.purple, C.cyan, C.pink];

// ── shared chart props ────────────────────────────────────────────────────
const TOOLTIP_STYLE = {
  background: '#1f2330',
  border: '1px solid rgba(255,255,255,0.12)',
  borderRadius: 4,
  fontSize: 11,
  color: '#dde4f0',
};
const AXIS_PROPS = {
  stroke: C.axis,
  fontSize: 10,
  tickLine: false,
  axisLine: false,
};

// ── sub-components ────────────────────────────────────────────────────────

function SectionHeader({ title, icon }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      background: C.section,
      border: `1px solid ${C.sectionBdr}`,
      borderRadius: '4px 4px 0 0',
      padding: '6px 14px',
      marginBottom: 0,
      marginTop: 24,
    }}>
      <span style={{ fontSize: 13 }}>{icon}</span>
      <span style={{ fontWeight: 700, fontSize: 12, color: '#c3cfe0', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
        {title}
      </span>
    </div>
  );
}

function Panel({ title, children, style }) {
  return (
    <div style={{
      background: C.panel,
      border: `1px solid ${C.panelBdr}`,
      borderRadius: 4,
      padding: '14px 16px 10px',
      ...style,
    }}>
      {title && (
        <div style={{ fontSize: 12, color: '#8fa3bf', fontWeight: 600, marginBottom: 10, letterSpacing: '0.03em' }}>
          {title}
        </div>
      )}
      {children}
    </div>
  );
}

function StatCard({ label, value, unit = '', color = '#eef1f7', sub }) {
  return (
    <Panel style={{ flex: 1, minWidth: 130 }}>
      <div style={{ fontSize: 10, color: '#738090', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{ fontSize: 28, fontWeight: 800, color, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
          {value ?? '—'}
        </span>
        {unit && <span style={{ fontSize: 12, color: '#738090' }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 10, color: '#738090', marginTop: 4 }}>{sub}</div>}
    </Panel>
  );
}

// tick-density reduction for crowded X axes
function SparseTick({ x, y, payload, index, nth = 10 }) {
  if (index % nth !== 0) return null;
  return <text x={x} y={y + 4} fill={C.axis} fontSize={9} textAnchor="middle">{payload.value}</text>;
}

// ── main component ────────────────────────────────────────────────────────

export default function MonitoringDashboard() {
  const [data, setData]       = useState(null);
  const [error, setError]     = useState(false);
  const [loading, setLoading] = useState(true);
  const [lastTs, setLastTs]   = useState(null);

  const fetchMetrics = useCallback(async () => {
    try {
      const r = await axios.get('/api/monitoring/metrics/');
      setData(r.data);
      setError(false);
      setLastTs(new Date().toLocaleTimeString());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    const id = setInterval(fetchMetrics, 15_000);
    return () => clearInterval(id);
  }, [fetchMetrics]);

  // ── derived ──────────────────────────────────────────────────────────
  const stats     = data?.stats            || {};
  const topEps    = data?.top_endpoints    || [];
  const trafficEp = data?.traffic_by_ep    || [];
  const trafficSt = data?.traffic_by_st    || [];
  const latPct    = data?.latency_pct      || [];
  const latByEp   = data?.latency_by_ep    || [];
  const cpu       = data?.resources?.cpu   || [];
  const mem       = data?.resources?.memory|| [];
  const fds       = data?.resources?.open_files || [];
  const sizeByEp  = data?.size_by_ep       || [];
  const throughput= data?.throughput        || [];

  const errorColor = stats.error_rate_pct > 0 ? C.red : C.green;

  // ── render ────────────────────────────────────────────────────────────
  return (
    <div style={{ background: C.bg, minHeight: '100vh', padding: '16px 20px', color: '#dde4f0', fontFamily: 'inherit' }}>

      {/* ── toolbar ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 10, color: '#5c6b7a', letterSpacing: '0.06em', marginBottom: 2 }}>
            Home / Dashboards / <span style={{ color: '#a0b0c0' }}>ML API Overview</span>
          </div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#edf2f8', letterSpacing: '0.01em' }}>
            📊 ML API Overview
          </h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {lastTs && (
            <span style={{ fontSize: 10, color: '#5c6b7a' }}>Last refresh: {lastTs}</span>
          )}
          <button
            onClick={fetchMetrics}
            style={{
              background: '#1f2330', border: '1px solid rgba(255,255,255,0.12)',
              color: '#c3cfe0', borderRadius: 4, padding: '5px 14px',
              cursor: 'pointer', fontSize: 12, fontWeight: 600,
              transition: 'background 0.15s',
            }}
            onMouseOver={e => e.currentTarget.style.background = '#2a2f42'}
            onMouseOut={e => e.currentTarget.style.background = '#1f2330'}
          >
            ↻ Refresh
          </button>
          <span style={{
            background: '#1e2b1e', border: '1px solid #2a4a2a',
            color: C.green, borderRadius: 4, padding: '4px 10px', fontSize: 11, fontWeight: 700,
          }}>
            Auto 15s
          </span>
        </div>
      </div>

      {error && (
        <div style={{ border: '1px solid #4a2020', background: '#2a1010', borderRadius: 4, padding: '8px 14px', marginBottom: 16, fontSize: 11, color: C.red }}>
          ⚠ Cannot reach /api/monitoring/metrics/ — backend may not have served any traffic yet. Navigate to other modules to generate metrics.
        </div>
      )}
      {loading && !data && (
        <div style={{ color: '#5c6b7a', fontSize: 12, marginBottom: 16 }}>Loading metrics…</div>
      )}

      {/* ── stat cards ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
        <StatCard label="Total Requests"      value={stats.total_requests ?? 0}       color={C.green} />
        <StatCard label="Predictions Made"    value={stats.prediction_requests ?? 0}  color={C.purple} />
        <StatCard
          label="Error Rate"
          value={stats.error_rate_pct != null ? `${stats.error_rate_pct}%` : '0%'}
          color={errorColor}
          sub="5xx / total (last 5 min)"
        />
        <StatCard label="P97 API Latency"     value={stats.p97_latency_ms ?? 0}  unit="ms"    color={C.yellow} />
        <StatCard label="Backend Uptime"      value={stats.uptime_hours ?? 0}    unit="hours" color={C.green}  />
        <StatCard label="Memory (RSS)"        value={stats.memory_mb ?? 0}       unit="MiB"   color={C.yellow} />
      </div>

      {/* ════════════════════════════════════════════════════════════════
          REQUEST TRAFFIC
      ═══════════════════════════════════════════════════════════════════ */}
      <SectionHeader title="Request Traffic" icon="📈" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 0 }}>

        {/* Request Rate by Endpoint */}
        <Panel title="Request Rate by Endpoint">
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <LineChart data={trafficEp} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
                <XAxis dataKey="ts" {...AXIS_PROPS} tick={<SparseTick nth={10} />} />
                <YAxis {...AXIS_PROPS} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Legend iconSize={8} wrapperStyle={{ fontSize: 10, paddingTop: 4 }} />
                {topEps.map((ep, i) => (
                  <Line
                    key={ep} type="monotone" dataKey={ep}
                    stroke={EP_COLORS[i % EP_COLORS.length]}
                    strokeWidth={1.5} dot={false} name={ep}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Request Rate by Status */}
        <Panel title="Request Rate by Status">
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <AreaChart data={trafficSt} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <defs>
                  {[['g2xx', C.green],['g3xx', C.yellow],['g4xx', C.orange],['g5xx', C.red]].map(([id, c]) => (
                    <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={c} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={c} stopOpacity={0.03} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
                <XAxis dataKey="ts" {...AXIS_PROPS} tick={<SparseTick nth={10} />} />
                <YAxis {...AXIS_PROPS} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Legend iconSize={8} wrapperStyle={{ fontSize: 10, paddingTop: 4 }} />
                <Area type="monotone" dataKey="2xx" stroke={C.green}  strokeWidth={1.5} fill="url(#g2xx)" name="2xx" />
                <Area type="monotone" dataKey="3xx" stroke={C.yellow} strokeWidth={1.5} fill="url(#g3xx)" name="3xx" />
                <Area type="monotone" dataKey="4xx" stroke={C.orange} strokeWidth={1.5} fill="url(#g4xx)" name="4xx" />
                <Area type="monotone" dataKey="5xx" stroke={C.red}    strokeWidth={1.5} fill="url(#g5xx)" name="5xx" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      {/* ════════════════════════════════════════════════════════════════
          LATENCY ANALYSIS
      ═══════════════════════════════════════════════════════════════════ */}
      <SectionHeader title="Latency Analysis" icon="⏱" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>

        {/* Latency Percentiles */}
        <Panel title="API Latency Percentiles (p50 / p95 / p99)">
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <LineChart data={latPct} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
                <XAxis dataKey="ts" {...AXIS_PROPS} tick={<SparseTick nth={10} />} />
                <YAxis {...AXIS_PROPS} unit="ms" />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v} ms`]} />
                <Legend iconSize={8} wrapperStyle={{ fontSize: 10, paddingTop: 4 }} />
                <Line type="monotone" dataKey="p50" stroke={C.green}  strokeWidth={1.5} dot={false} name="p50" />
                <Line type="monotone" dataKey="p95" stroke={C.yellow} strokeWidth={1.5} dot={false} name="p95" />
                <Line type="monotone" dataKey="p99" stroke={C.red}    strokeWidth={1.5} dot={false} name="p99" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Latency by Endpoint (horizontal bar) */}
        <Panel title="Latency by Endpoint (ms)">
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <BarChart
                data={latByEp}
                layout="vertical"
                margin={{ top: 4, right: 16, left: 60, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} horizontal={false} />
                <XAxis type="number" {...AXIS_PROPS} unit="ms" />
                <YAxis type="category" dataKey="endpoint" {...AXIS_PROPS} width={60} fontSize={9} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v} ms`]} />
                <Bar dataKey="avg_ms" name="Avg latency" radius={[0, 3, 3, 0]}>
                  {latByEp.map((_, i) => (
                    <Cell key={i} fill={EP_COLORS[i % EP_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      {/* ════════════════════════════════════════════════════════════════
          BACKEND RESOURCES
      ═══════════════════════════════════════════════════════════════════ */}
      <SectionHeader title="Backend Resources" icon="🖥" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>

        {/* CPU */}
        <Panel title="CPU Usage">
          <div style={{ height: 150 }}>
            <ResponsiveContainer>
              <AreaChart data={cpu} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
                <defs>
                  <linearGradient id="gcpu" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={C.orange} stopOpacity={0.45} />
                    <stop offset="95%" stopColor={C.orange} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
                <XAxis dataKey="ts" {...AXIS_PROPS} tick={<SparseTick nth={6} />} />
                <YAxis {...AXIS_PROPS} unit="%" />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v}%`, 'CPU']} />
                <Area type="monotone" dataKey="value" stroke={C.orange} strokeWidth={1.5} fill="url(#gcpu)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Memory */}
        <Panel title="Memory Usage">
          <div style={{ height: 150 }}>
            <ResponsiveContainer>
              <AreaChart data={mem} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
                <defs>
                  <linearGradient id="gmem" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={C.yellow} stopOpacity={0.45} />
                    <stop offset="95%" stopColor={C.yellow} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
                <XAxis dataKey="ts" {...AXIS_PROPS} tick={<SparseTick nth={6} />} />
                <YAxis {...AXIS_PROPS} unit=" MB" />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v} MB`, 'Memory']} />
                <Area type="monotone" dataKey="value" stroke={C.yellow} strokeWidth={1.5} fill="url(#gmem)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Open File Descriptors */}
        <Panel title="Open File Descriptors">
          <div style={{ height: 150 }}>
            <ResponsiveContainer>
              <AreaChart data={fds} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
                <defs>
                  <linearGradient id="gfds" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={C.blue} stopOpacity={0.45} />
                    <stop offset="95%" stopColor={C.blue} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
                <XAxis dataKey="ts" {...AXIS_PROPS} tick={<SparseTick nth={6} />} />
                <YAxis {...AXIS_PROPS} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [v, 'FDs']} />
                <Area type="monotone" dataKey="value" stroke={C.blue} strokeWidth={1.5} fill="url(#gfds)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      {/* ════════════════════════════════════════════════════════════════
          RESPONSE SIZE ANALYSIS
      ═══════════════════════════════════════════════════════════════════ */}
      <SectionHeader title="Response Size Analysis" icon="📦" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>

        {/* Avg Response Size by Endpoint */}
        <Panel title="Avg Response Size by Endpoint">
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <BarChart
                data={sizeByEp}
                layout="vertical"
                margin={{ top: 4, right: 16, left: 60, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} horizontal={false} />
                <XAxis type="number" {...AXIS_PROPS} unit=" B" />
                <YAxis type="category" dataKey="endpoint" {...AXIS_PROPS} width={60} fontSize={9} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v} bytes`]} />
                <Bar dataKey="avg_bytes" name="Avg size" fill={C.cyan} radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* Throughput */}
        <Panel title="Request Throughput (bytes/sec)">
          <div style={{ height: 180 }}>
            <ResponsiveContainer>
              <AreaChart data={throughput} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gtp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={C.pink} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={C.pink} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke={C.grid} vertical={false} />
                <XAxis dataKey="ts" {...AXIS_PROPS} tick={<SparseTick nth={10} />} />
                <YAxis {...AXIS_PROPS} unit=" B/s" />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v} B/s`, 'Throughput']} />
                <Area type="monotone" dataKey="value" stroke={C.pink} strokeWidth={1.5} fill="url(#gtp)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      {/* footer spacing */}
      <div style={{ height: 32 }} />
    </div>
  );
}
