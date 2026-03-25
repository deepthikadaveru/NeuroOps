import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, AreaChart, Area
} from 'recharts';

const API = '/api';

const getRiskColor = (risk) => ({
  low: '#22c55e', medium: '#f59e0b',
  high: '#f97316', critical: '#ef4444', unknown: '#6b7280'
})[risk] || '#6b7280';

const getHealthColor = (score) => {
  if (score >= 75) return '#22c55e';
  if (score >= 50) return '#f59e0b';
  return '#ef4444';
};

const severityColor = (s) => ({
  critical: '#ef4444', high: '#f97316',
  medium: '#f59e0b', low: '#22c55e', none: '#22c55e'
})[s] || '#6b7280';

const fmt = (ts) => ts ? ts.slice(11, 19) : '—';

// 10 demo scenarios for the trigger panel
const DEMO_SCENARIOS = [
  { id: 'payment_failure',    label: 'Payment Failure',    color: '#ef4444', icon: '💳' },
  { id: 'traffic_overload',   label: 'Traffic Overload',   color: '#f97316', icon: '📈' },
  { id: 'memory_leak',        label: 'Memory Leak',        color: '#f59e0b', icon: '🧠' },
  { id: 'bad_deployment',     label: 'Bad Deployment',     color: '#ef4444', icon: '🚀' },
  { id: 'db_slowdown',        label: 'DB Slowdown',        color: '#f97316', icon: '🗄️' },
  { id: 'cascade_failure',    label: 'Cascade Failure',    color: '#ef4444', icon: '💥' },
  { id: 'network_latency',    label: 'Network Latency',    color: '#f59e0b', icon: '🌐' },
  { id: 'recovery',           label: 'Recovery',           color: '#22c55e', icon: '🔄' },
  { id: 'predicted_failure',  label: 'Predicted Failure',  color: '#f59e0b', icon: '🔮' },
  { id: 'resource_exhaustion',label: 'Resource Exhaustion',color: '#f97316', icon: '⚡' },
];

export default function App() {
  const [status,    setStatus]    = useState(null);
  const [history,   setHistory]   = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [actions,   setActions]   = useState([]);
  const [updated,   setUpdated]   = useState(null);
  const [prevHealth,setPrevHealth]= useState(null);
  const [flash,     setFlash]     = useState(false);
  const [triggering,setTriggering]= useState(null);  // scenario id being triggered
  const [triggerMsg,setTriggerMsg]= useState(null);  // last trigger result

  const fetchData = useCallback(async () => {
    try {
      const [sRes, hRes, aRes, acRes] = await Promise.all([
        fetch(`${API}/status`),
        fetch(`${API}/features/history`),
        fetch(`${API}/anomalies`),
        fetch(`${API}/actions`),
      ]);
      const s  = await sRes.json();
      const h  = await hRes.json();
      const a  = await aRes.json();
      const ac = await acRes.json();

      if (s.anomaly?.is_anomaly && status && !status.anomaly?.is_anomaly) {
        setFlash(true);
        setTimeout(() => setFlash(false), 1000);
      }

      setPrevHealth(status?.health_score);
      setStatus(s);
      setHistory((h.data || []).map(d => ({
        time:   fmt(d.timestamp),
        health: d.health_score ? +d.health_score.toFixed(1) : 0,
        errors: +(d.raw_error_rate * 100).toFixed(1),
        cpu:    +(d.raw_cpu * 100).toFixed(1),
        latency: +(d.raw_latency * 1000).toFixed(0),
      })));
      setAnomalies(a.recent || []);
      setActions(ac.recent || []);
      setUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      console.error(e);
    }
  }, [status]);

  useEffect(() => {
    fetchData();
    const t = setInterval(fetchData, 4000);
    return () => clearInterval(t);
  }, [fetchData]);

  const triggerScenario = async (scenarioId) => {
    setTriggering(scenarioId);
    setTriggerMsg(null);
    try {
      const res = await fetch(`http://localhost:5001/demo/${scenarioId}`);
      const data = await res.json();
      setTriggerMsg({
        ok:  res.ok,
        text: res.ok
          ? `✓ ${data.description || scenarioId} triggered — auto-recovers in ${data.auto_recover_in}s`
          : `✗ ${data.status || 'trigger failed'}`,
      });
    } catch (e) {
      setTriggerMsg({ ok: false, text: `✗ Cannot reach API service: ${e.message}` });
    } finally {
      setTriggering(null);
      setTimeout(() => setTriggerMsg(null), 6000);
    }
  };

  if (!status) return (
    <div style={S.splash}>
      <div style={S.splashIcon}>⬡</div>
      <div style={S.splashText}>NEURO-OPS</div>
      <div style={S.splashSub}>Initializing monitoring systems...</div>
    </div>
  );

  const anomaly    = status.anomaly    || {};
  const prediction = status.prediction || {};
  const rootCause  = status.root_cause || {};
  const project    = status.project    || {};
  const isAnomaly  = !!anomaly.is_anomaly;
  const health     = status.health_score || 0;
  const risk       = prediction.risk_level || 'unknown';
  const riskCol    = getRiskColor(risk);
  const healthCol  = getHealthColor(health);
  const healthDelta = prevHealth != null ? (health - prevHealth).toFixed(1) : null;

  return (
    <div style={{ ...S.page, ...(flash ? S.flashPage : {}) }}>

      {/* ── Header ── */}
      <div style={S.header}>
        <div style={S.headerLeft}>
          <span style={S.logo}>⬡ NEURO-OPS</span>
          <span style={S.version}>v2.0 · AIOps Platform</span>
        </div>
        <div style={S.headerCenter}>
          <div style={{
            ...S.systemStatus,
            background: isAnomaly ? '#ef444415' : '#22c55e15',
            border: `1px solid ${isAnomaly ? '#ef4444' : '#22c55e'}`,
            color:  isAnomaly ? '#ef4444' : '#22c55e',
          }}>
            <span style={{
              ...S.statusDot,
              background: isAnomaly ? '#ef4444' : '#22c55e',
              animation:  isAnomaly ? 'pulse 1s infinite' : 'pulse 2s infinite',
            }} />
            {isAnomaly ? '⚠ INCIDENT DETECTED' : '✓ SYSTEMS NORMAL'}
          </div>
        </div>
        <div style={S.headerRight}>
          <div style={S.projectBadge}>
            <span style={S.projectDot} />
            {project.name || 'Neuro-Ops Demo'}
          </div>
          <div style={S.updateTime}>↻ {updated}</div>
        </div>
      </div>

      {/* ── Incident Banner ── */}
      {isAnomaly && rootCause.human_label && (
        <div style={{
          ...S.incidentBanner,
          borderColor: severityColor(rootCause.severity),
          background: `${severityColor(rootCause.severity)}12`,
        }}>
          <span style={{ color: severityColor(rootCause.severity), fontWeight: 700 }}>
            ⚡ {rootCause.human_label?.toUpperCase()}
          </span>
          <span style={S.bannerDesc}>{rootCause.description}</span>
          {rootCause.action && (
            <span style={{ ...S.bannerAction, color: severityColor(rootCause.severity) }}>
              → Auto-healing: {rootCause.action.replace(/_/g, ' ')}
            </span>
          )}
        </div>
      )}

      {/* ── Prediction Banner ── */}
      {prediction.failure_predicted && (
        <div style={S.predBanner}>
          <span style={{ color: '#f59e0b', fontWeight: 700 }}>⚡ FAILURE PREDICTED</span>
          <span style={S.bannerDesc}>
            Health forecast: {prediction.predicted_health} in ~{prediction.time_to_failure_seconds}s
          </span>
          <span style={{ color: '#f59e0b', fontSize: 11 }}>Neuro-Ops is pre-emptively intervening</span>
        </div>
      )}

      {/* ── KPI Row ── */}
      <div style={S.kpiRow}>
        <KPI
          label="System Health"
          value={health.toFixed(1)}
          unit="/100"
          color={healthCol}
          delta={healthDelta}
          sub={`Model: ${status.model_trained ? 'trained ✓' : 'warming up'}`}
          big
        />
        <KPI
          label="Risk Level"
          value={risk.toUpperCase()}
          color={riskCol}
          sub={`Predicted: ${prediction.predicted_health ?? '—'}`}
        />
        <KPI
          label="Error Rate"
          value={`${(status.raw_error_rate * 100).toFixed(1)}`}
          unit="%"
          color={status.raw_error_rate > 0.3 ? '#ef4444' : status.raw_error_rate > 0.1 ? '#f59e0b' : '#22c55e'}
          sub={`Trend: ${status.error_trend || '—'}`}
        />
        <KPI
          label="CPU Trend"
          value={(status.cpu_trend || '—').toUpperCase()}
          color={status.cpu_trend === 'rising' ? '#f97316' : '#22c55e'}
          sub={`Latency: ${status.latency_trend || '—'}`}
        />
        <KPI
          label="Incidents"
          value={anomalies.length}
          color={anomalies.length > 0 ? '#ef4444' : '#22c55e'}
          sub={`Actions taken: ${actions.filter(a => a.success).length}`}
        />
      </div>

      {/* ── Charts ── */}
      <div style={S.chartsRow}>
        <ChartCard title="System Health Score" color="#22c55e" data={history} dataKey="health"  domain={[0, 100]} area />
        <ChartCard title="Payment Error Rate %" color="#ef4444" data={history} dataKey="errors"  domain={[0, 100]} area />
        <ChartCard title="CPU Usage %"          color="#f59e0b" data={history} dataKey="cpu"     domain={[0, 100]} />
      </div>

      {/* ── Bottom Panels ── */}
      <div style={S.bottomRow}>

        {/* Incident Log */}
        <Panel title="⚠ Incident Log" count={anomalies.length} countColor="#ef4444">
          {anomalies.length === 0
            ? <Empty text="No incidents — all payments processing normally" />
            : [...anomalies].reverse().map((a, i) => (
              <div key={i} style={S.logRow}>
                <div style={S.logTime}>{fmt(a.timestamp)}</div>
                <div style={S.logBody}>
                  <div style={{ ...S.logLabel, color: severityColor(a.root_cause?.severity || 'medium') }}>
                    {a.root_cause?.human_label || a.root_cause?.root_cause || 'Anomaly Detected'}
                  </div>
                  <div style={S.logDesc}>
                    {a.root_cause?.description
                      ? a.root_cause.description.slice(0, 90) + (a.root_cause.description.length > 90 ? '...' : '')
                      : `Score: ${a.anomaly?.anomaly_score?.toFixed(3)} · Health: ${a.health_score?.toFixed(1)}`
                    }
                  </div>
                </div>
              </div>
            ))}
        </Panel>

        {/* Auto-Actions */}
        <Panel title="⚡ Auto-Actions" count={actions.filter(a => a.success).length} countColor="#22c55e">
          {actions.length === 0
            ? <Empty text="No actions taken yet" />
            : [...actions].reverse().map((a, i) => (
              <div key={i} style={S.logRow}>
                <div style={S.logTime}>{fmt(a.timestamp)}</div>
                <div style={S.logBody}>
                  <div style={{ ...S.logLabel, color: a.success ? '#22c55e' : '#ef4444' }}>
                    {a.success ? '✓' : '✗'} {a.human_label || a.action?.replace(/_/g, ' ')}
                  </div>
                  <div style={S.logDesc}>{a.reason?.slice(0, 80) || '—'}</div>
                </div>
              </div>
            ))}
        </Panel>

        {/* Root Cause Diagnosis */}
        <Panel title="🔍 Diagnosis">
          {!rootCause.root_cause || rootCause.root_cause === null
            ? (
              <div style={S.normalState}>
                <div style={S.normalIcon}>✓</div>
                <div style={S.normalText}>All payment systems operating normally</div>
                <div style={S.normalSub}>Neuro-Ops is actively monitoring</div>
              </div>
            ) : (
              <>
                <div style={S.diagRow}>
                  <span style={S.diagLabel}>Issue</span>
                  <span style={{ ...S.diagValue, color: severityColor(rootCause.severity) }}>
                    {rootCause.human_label || rootCause.root_cause}
                  </span>
                </div>
                <div style={S.diagRow}>
                  <span style={S.diagLabel}>Severity</span>
                  <span style={{
                    ...S.diagBadge,
                    background: `${severityColor(rootCause.severity)}22`,
                    color: severityColor(rootCause.severity),
                    border: `1px solid ${severityColor(rootCause.severity)}44`,
                  }}>
                    {(rootCause.severity || 'unknown').toUpperCase()}
                  </span>
                </div>
                <div style={S.diagRow}>
                  <span style={S.diagLabel}>Response</span>
                  <span style={{ ...S.diagValue, color: '#a78bfa' }}>
                    {rootCause.action?.replace(/_/g, ' ') || '—'}
                  </span>
                </div>
                <div style={S.diagDesc}>{rootCause.description}</div>
                {rootCause.affected_services?.length > 0 && (
                  <div style={S.affectedRow}>
                    {rootCause.affected_services.map((s, i) => (
                      <span key={i} style={S.serviceTag}>{s}</span>
                    ))}
                  </div>
                )}
              </>
            )}
        </Panel>
      </div>

      {/* ── Demo Trigger Panel ── */}
      <div style={S.demoPanel}>
        <div style={S.demoPanelHeader}>
          <span style={S.demoPanelTitle}>🎬 DEMO — TRIGGER SCENARIOS</span>
          <span style={S.demoPanelSub}>Click to inject a failure signature · Neuro-Ops detects and responds automatically</span>
        </div>
        {triggerMsg && (
          <div style={{
            ...S.triggerMsg,
            color: triggerMsg.ok ? '#22c55e' : '#ef4444',
            borderColor: triggerMsg.ok ? '#22c55e44' : '#ef444444',
            background: triggerMsg.ok ? '#22c55e0a' : '#ef44440a',
          }}>
            {triggerMsg.text}
          </div>
        )}
        <div style={S.demoGrid}>
          {DEMO_SCENARIOS.map(({ id, label, color, icon }) => (
            <button
              key={id}
              style={{
                ...S.demoBtn,
                borderColor: triggering === id ? color : `${color}44`,
                color:       triggering === id ? '#f9fafb' : color,
                background:  triggering === id ? `${color}33` : `${color}0d`,
                opacity:     triggering && triggering !== id ? 0.5 : 1,
              }}
              onClick={() => triggerScenario(id)}
              disabled={!!triggering}
            >
              <span style={S.demoBtnIcon}>{icon}</span>
              <span style={S.demoBtnLabel}>{label}</span>
            </button>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

/* ── Sub-components ── */

function KPI({ label, value, unit, color, sub, delta, big }) {
  return (
    <div style={{ ...S.kpi, ...(big ? S.kpiBig : {}) }}>
      <div style={S.kpiLabel}>{label}</div>
      <div style={{ ...S.kpiValue, color, fontSize: big ? 38 : 28 }}>
        {value}
        {unit && <span style={S.kpiUnit}>{unit}</span>}
        {delta != null && (
          <span style={{ fontSize: 13, color: +delta >= 0 ? '#22c55e' : '#ef4444', marginLeft: 6 }}>
            {+delta >= 0 ? '↑' : '↓'}{Math.abs(delta)}
          </span>
        )}
      </div>
      <div style={S.kpiSub}>{sub}</div>
    </div>
  );
}

function ChartCard({ title, data, dataKey, color, domain, area }) {
  return (
    <div style={S.chartCard}>
      <div style={S.chartTitle}>{title}</div>
      <ResponsiveContainer width="100%" height={110}>
        {area ? (
          <AreaChart data={data}>
            <defs>
              <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff06" />
            <XAxis dataKey="time" tick={{ fill: '#4b5563', fontSize: 9 }} interval="preserveStartEnd" />
            <YAxis domain={domain} tick={{ fill: '#4b5563', fontSize: 9 }} width={28} />
            <Tooltip contentStyle={{ background: '#111827', border: `1px solid ${color}44`, borderRadius: 6, fontSize: 11 }} itemStyle={{ color }} />
            <Area type="monotone" dataKey={dataKey} stroke={color} fill={`url(#grad-${dataKey})`} strokeWidth={2} dot={false} />
          </AreaChart>
        ) : (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff06" />
            <XAxis dataKey="time" tick={{ fill: '#4b5563', fontSize: 9 }} interval="preserveStartEnd" />
            <YAxis domain={domain} tick={{ fill: '#4b5563', fontSize: 9 }} width={28} />
            <Tooltip contentStyle={{ background: '#111827', border: `1px solid ${color}44`, borderRadius: 6, fontSize: 11 }} itemStyle={{ color }} />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function Panel({ title, count, countColor, children }) {
  return (
    <div style={S.panel}>
      <div style={S.panelHeader}>
        <span style={S.panelTitle}>{title}</span>
        {count != null && (
          <span style={{ ...S.panelCount, color: countColor, borderColor: `${countColor}44` }}>
            {count}
          </span>
        )}
      </div>
      <div style={S.panelBody}>{children}</div>
    </div>
  );
}

function Empty({ text }) {
  return (
    <div style={S.empty}>
      <div style={{ fontSize: 20, marginBottom: 8 }}>✓</div>
      {text}
    </div>
  );
}

/* ── Styles ── */
const S = {
  page: {
    minHeight:   '100vh',
    background:  '#030712',
    color:       '#f9fafb',
    fontFamily:  "'DM Sans', 'Segoe UI', sans-serif",
    padding:     '16px 20px',
    transition:  'background 0.3s',
  },
  flashPage: { background: '#1a0a0a' },
  splash: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100vh', background: '#030712',
  },
  splashIcon: { fontSize: 48, color: '#7c6eff', marginBottom: 12 },
  splashText: { fontSize: 32, fontWeight: 700, letterSpacing: 8, color: '#f9fafb', marginBottom: 8 },
  splashSub:  { fontSize: 13, color: '#6b7280', letterSpacing: 2 },

  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12, paddingBottom: 12, borderBottom: '1px solid #ffffff0a',
  },
  headerLeft:    { display: 'flex', alignItems: 'baseline', gap: 12 },
  logo:          { fontSize: 20, fontWeight: 700, color: '#7c6eff', letterSpacing: 3 },
  version:       { fontSize: 11, color: '#4b5563', letterSpacing: 1 },
  headerCenter:  { flex: 1, display: 'flex', justifyContent: 'center' },
  systemStatus: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '6px 18px', borderRadius: 20, fontSize: 12, fontWeight: 600, letterSpacing: 1,
  },
  statusDot:  { width: 7, height: 7, borderRadius: '50%', display: 'inline-block' },
  headerRight:  { display: 'flex', alignItems: 'center', gap: 12 },
  projectBadge: {
    display: 'flex', alignItems: 'center', gap: 6,
    background: '#ffffff08', border: '1px solid #ffffff10',
    borderRadius: 20, padding: '4px 12px', fontSize: 11, color: '#9ca3af',
  },
  projectDot: { width: 6, height: 6, borderRadius: '50%', background: '#7c6eff' },
  updateTime: { fontSize: 11, color: '#374151' },

  incidentBanner: {
    display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
    padding: '10px 16px', borderRadius: 8, border: '1px solid',
    marginBottom: 12, fontSize: 12,
  },
  predBanner: {
    display: 'flex', alignItems: 'center', gap: 16,
    padding: '10px 16px', borderRadius: 8, border: '1px solid #f59e0b44',
    background: '#f59e0b0a', marginBottom: 12, fontSize: 12,
  },
  bannerDesc:   { color: '#d1d5db', flex: 1 },
  bannerAction: { fontSize: 11, fontWeight: 600 },

  kpiRow: {
    display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr 1fr',
    gap: 12, marginBottom: 12,
  },
  kpi:      { background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, padding: '14px 16px' },
  kpiBig:   { background: '#0a0f1e', border: '1px solid #1e3a5f' },
  kpiLabel: { fontSize: 10, letterSpacing: 2, color: '#4b5563', textTransform: 'uppercase', marginBottom: 6 },
  kpiValue: { fontWeight: 700, letterSpacing: 1, lineHeight: 1 },
  kpiUnit:  { fontSize: 13, opacity: 0.6, marginLeft: 3, fontWeight: 400 },
  kpiSub:   { fontSize: 10, color: '#374151', marginTop: 6 },

  chartsRow: { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 12 },
  chartCard: { background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, padding: '14px 16px' },
  chartTitle:{ fontSize: 10, letterSpacing: 2, color: '#4b5563', textTransform: 'uppercase', marginBottom: 10 },

  bottomRow: { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 12 },
  panel:    { background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10, overflow: 'hidden' },
  panelHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '12px 16px', borderBottom: '1px solid #1e293b',
  },
  panelTitle: { fontSize: 10, letterSpacing: 2, color: '#6b7280', textTransform: 'uppercase', fontWeight: 600 },
  panelCount: { fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10, border: '1px solid' },
  panelBody:  { padding: '12px 16px', maxHeight: 220, overflowY: 'auto' },

  logRow:  { display: 'flex', gap: 10, marginBottom: 10, alignItems: 'flex-start' },
  logTime: { fontSize: 10, color: '#374151', fontFamily: 'monospace', minWidth: 56, paddingTop: 2 },
  logBody: { flex: 1 },
  logLabel:{ fontSize: 12, fontWeight: 600, marginBottom: 2 },
  logDesc: { fontSize: 11, color: '#6b7280', lineHeight: 1.4 },

  normalState: { textAlign: 'center', padding: '20px 0' },
  normalIcon:  { fontSize: 28, color: '#22c55e', marginBottom: 8 },
  normalText:  { fontSize: 13, color: '#d1d5db', fontWeight: 500, marginBottom: 4 },
  normalSub:   { fontSize: 11, color: '#4b5563' },
  diagRow:     { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  diagLabel:   { fontSize: 11, color: '#4b5563', letterSpacing: 1 },
  diagValue:   { fontSize: 13, fontWeight: 600 },
  diagBadge:   { fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4, letterSpacing: 1 },
  diagDesc:    { fontSize: 11, color: '#6b7280', lineHeight: 1.6, marginTop: 8, marginBottom: 10 },
  affectedRow: { display: 'flex', gap: 6, flexWrap: 'wrap' },
  serviceTag:  {
    fontSize: 10, padding: '2px 8px', borderRadius: 4,
    background: '#7c6eff22', color: '#a78bfa', border: '1px solid #7c6eff33',
  },
  empty: { textAlign: 'center', color: '#374151', fontSize: 12, padding: '20px 0', lineHeight: 2 },

  // Demo trigger panel
  demoPanel: {
    background: '#0a0f1e', border: '1px solid #1e3a5f',
    borderRadius: 10, padding: '16px', marginTop: 4,
  },
  demoPanelHeader: {
    display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 12,
  },
  demoPanelTitle: {
    fontSize: 10, letterSpacing: 2, color: '#7c6eff',
    textTransform: 'uppercase', fontWeight: 700,
  },
  demoPanelSub: { fontSize: 11, color: '#374151' },
  triggerMsg: {
    fontSize: 12, padding: '8px 12px', borderRadius: 6,
    border: '1px solid', marginBottom: 12, fontFamily: 'monospace',
  },
  demoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: 8,
  },
  demoBtn: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    gap: 5, padding: '10px 8px', borderRadius: 8,
    border: '1px solid', cursor: 'pointer',
    transition: 'all 0.15s', fontSize: 11, fontWeight: 600,
    letterSpacing: 0.5, background: 'transparent',
    fontFamily: "'DM Sans', sans-serif",
  },
  demoBtnIcon:  { fontSize: 18 },
  demoBtnLabel: { textAlign: 'center', lineHeight: 1.3 },
};