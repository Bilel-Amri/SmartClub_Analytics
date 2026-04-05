import React, { useState, useRef, useEffect, useCallback } from 'react';

// ─── Constants ────────────────────────────────────────────────────────────────

const LANGUAGES = [
  { code: 'auto', label: 'Auto' },
  { code: 'en',   label: 'EN' },
  { code: 'fr',   label: 'FR' },
  { code: 'ar',   label: 'AR' },
  { code: 'tn',   label: 'TN' },
];

const QUICK_CHIPS = [
  { label: '🔴 Risk 7d',    message: 'Predict injury risk 7 days for {{player}}' },
  { label: '📅 Risk 30d',   message: 'Predict injury risk 30 days for {{player}}' },
  { label: '📈 ACWR Trend', message: 'Show ACWR and training load trend for {{player}}' },
  { label: '🥗 Nutrition',  message: 'Generate nutrition plan for {{player}} training day' },
  { label: '🍽️ Meal Calc',  message: 'Calculate: chicken breast 150g, rice 200g, broccoli 100g' },
  { label: '👥 Squad',      message: 'Squad overview' },
];

const RTL_LANGS = new Set(['ar', 'tn']);

const SESSION_KEY = 'smartclub_chat_session_id';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTs(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatReply(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code class="inline-code">$1</code>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br/>');
}

function bandColor(band) {
  const b = (band || '').toLowerCase();
  if (b === 'high')                      return '#ef4444';
  if (b === 'medium' || b === 'caution') return '#f59e0b';
  return '#22c55e';
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function RiskCard({ grounding }) {
  if (!grounding?.risk_probability) return null;
  const pct   = Math.round(grounding.risk_probability * 100);
  const band  = grounding.band || '';
  const color = bandColor(band);
  return (
    <div style={{
      margin: '8px 0', padding: '12px 16px',
      background: 'var(--bg-card)', border: `1px solid ${color}44`,
      borderLeft: `4px solid ${color}`, borderRadius: '8px',
      fontSize: '0.82rem',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontWeight: '700', color: 'var(--text-primary)' }}>
          {grounding.player_name} — {grounding.horizon_days}d Risk
        </span>
        <span style={{
          background: color, color: '#fff', borderRadius: '8px',
          padding: '2px 10px', fontWeight: '700',
        }}>
          {pct}% {band}
        </span>
      </div>
      {grounding.top_factors?.length > 0 && (
        <div style={{ color: 'var(--text-secondary)' }}>
          <strong>Top factors:</strong>{' '}
          {grounding.top_factors.slice(0, 3).map((f, i) => (
            <span key={i} style={{ marginRight: '8px' }}>
              {f.name.replace(/_/g, ' ')}
              {f.impact != null ? ` (${(f.impact > 0 ? '+' : '') + f.impact.toFixed(2)})` : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function CandidateChooser({ candidates, onSelect }) {
  if (!candidates?.length) return null;
  return (
    <div style={{
      margin: '8px 0', padding: '12px',
      background: 'var(--bg-card)', border: '1px solid var(--border-color)',
      borderRadius: '8px', fontSize: '0.82rem',
    }}>
      <div style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>
        Found {candidates.length} players — choose one:
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {candidates.map((c, i) => (
          <button
            key={i}
            onClick={() => onSelect(c)}
            style={{
              padding: '4px 12px', fontSize: '0.78rem',
              background: 'var(--bg-card)', border: '1px solid var(--neon-cyan)',
              borderRadius: '20px', color: 'var(--neon-cyan)', cursor: 'pointer',
            }}
          >
            {c.name}{c.position ? ` (${c.position})` : ''}{c.age ? `, ${c.age}` : ''}
          </button>
        ))}
      </div>
    </div>
  );
}

function ToolTrace({ toolCalls, grounding }) {
  const [open, setOpen] = useState(false);
  if (!toolCalls?.length) return null;
  return (
    <div style={{ marginTop: '6px' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none', border: 'none', color: 'var(--text-muted)',
          fontSize: '0.72rem', cursor: 'pointer', padding: 0,
          display: 'flex', alignItems: 'center', gap: '4px',
        }}
      >
        {open ? '▼' : '▶'} How I answered ({toolCalls.length} tool call{toolCalls.length > 1 ? 's' : ''})
      </button>
      {open && (
        <div style={{
          marginTop: '6px', padding: '8px 12px',
          background: 'rgba(0,0,0,0.2)', borderRadius: '6px',
          fontSize: '0.72rem', color: 'var(--text-muted)',
        }}>
          {toolCalls.map((tc, i) => (
            <div key={i} style={{ marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ color: tc.ok ? '#22c55e' : '#ef4444' }}>{tc.ok ? '✓' : '✗'}</span>
              <code style={{ color: 'var(--neon-cyan)', background: 'none' }}>{tc.tool}</code>
              {Object.entries(tc.args || {}).map(([k, v]) => (
                <span key={k}>{k}=<em>{String(v)}</em></span>
              ))}
              {tc.latency_ms != null && (
                <span style={{ marginLeft: 'auto', opacity: 0.6 }}>{tc.latency_ms}ms</span>
              )}
            </div>
          ))}
          {grounding?.player_name && (
            <div style={{ marginTop: '6px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px' }}>
              Grounded on: <strong>{grounding.player_name}</strong>
              {grounding.horizon_days ? ` · ${grounding.horizon_days}d horizon` : ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg, onSelectCandidate }) {
  const isUser = msg.role === 'user';
  return (
    <div
      className={`chat-row ${isUser ? 'user-row' : 'bot-row'}`}
      dir={msg.rtl ? 'rtl' : 'ltr'}
    >
      {!isUser && <div className="bot-avatar">🤖</div>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className={`chat-bubble ${isUser ? 'user-bubble' : 'bot-bubble'}`}>
          {isUser ? (
            msg.text
          ) : msg.streaming && !msg.text ? (
            // Still waiting for first token — show typing dots
            <span className="typing">
              <span className="dot" /><span className="dot" /><span className="dot" />
            </span>
          ) : (
            // Text streaming or complete
            <>
              <span dangerouslySetInnerHTML={{ __html: formatReply(msg.text) }} />
              {msg.streaming && (
                <span style={{
                  display: 'inline-block', width: '2px', height: '1em',
                  background: 'var(--neon-cyan)', marginLeft: '2px',
                  verticalAlign: 'text-bottom', animation: 'blink 1s step-end infinite',
                }} />
              )}
            </>
          )}
        </div>
        {!isUser && msg.grounding?.candidates && (
          <CandidateChooser candidates={msg.grounding.candidates} onSelect={onSelectCandidate} />
        )}
        {!isUser && <RiskCard grounding={msg.grounding} />}
        {!isUser && <ToolTrace toolCalls={msg.toolCalls} grounding={msg.grounding} />}
        <div style={{
          fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '3px',
          textAlign: isUser ? 'right' : 'left',
        }}>
          {msg.ts ? formatTs(msg.ts) : ''}
          {!isUser && msg.language && msg.language !== 'en' && (
            <span style={{ marginLeft: '6px', opacity: 0.6 }}>[{msg.language.toUpperCase()}]</span>
          )}
        </div>
      </div>
      {isUser && <div className="user-avatar">👤</div>}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Chatbot() {
  const [messages, setMessages] = useState([{
    id: 'welcome', role: 'bot', rtl: false, ts: new Date().toISOString(),
    text: 'Hello! 👋 I\'m **SmartClub AI** — powered by Groq (llama-3.1-8b-instant).\n\nI can:\n• Predict injury risk (7d / 30d)\n• Show training load & ACWR trends\n• Retrieve nutrition plans & meal calcs\n• Search players & supplements\n\nType *help* or pick a quick action below.',
    toolCalls: null, grounding: null, streaming: false,
  }]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const [language, setLanguage] = useState('auto');
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null);
  const [lastPlayer, setLastPlayer] = useState(null);
  const bottomRef = useRef(null);

  const isRtl = RTL_LANGS.has(language);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, { ts: new Date().toISOString(), ...msg }]);
  }, []);

  const send = useCallback(async (text) => {
    const raw = (text || input).trim();
    if (!raw || loading) return;
    setInput('');

    const msg = raw.replace('{{player}}', lastPlayer ? lastPlayer.name : '[player name]');
    const userIsRtl = RTL_LANGS.has(language);
    addMessage({ role: 'user', text: msg, rtl: userIsRtl });
    setLoading(true);

    // Add an empty streaming bot message immediately
    const botId = `bot-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: botId, role: 'bot', text: '', streaming: true,
      ts: new Date().toISOString(), toolCalls: null, grounding: null, language: null, rtl: false,
    }]);

    try {
      const response = await fetch('/api/chat-llm/stream/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: sessionId, language }),
      });

      if (!response.ok) {
        await response.text();
        setMessages(prev => prev.map(m =>
          m.id === botId
            ? { ...m, text: `❌ Server error ${response.status}`, streaming: false }
            : m
        ));
        return;
      }

      const reader = response.body.getReader();
      const decoder = new window.TextDecoder();
      let buffer = '';
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // keep incomplete trailing chunk

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;
          let data;
          try { data = JSON.parse(line.slice(5).trim()); } catch { continue; }

          // Progressive text chunk
          if (data.chunk !== undefined) {
            fullText += data.chunk;
            setMessages(prev => prev.map(m =>
              m.id === botId ? { ...m, text: fullText } : m
            ));
          }

          // Final done event — attach metadata
          if (data.done) {
            const lang = data.language || 'en';
            setMessages(prev => prev.map(m =>
              m.id === botId
                ? { ...m, text: fullText || m.text, streaming: false,
                    toolCalls: data.tool_calls || [], grounding: data.grounding || {},
                    language: lang, rtl: RTL_LANGS.has(lang) }
                : m
            ));
            if (data.session_id && data.session_id !== sessionId) {
              setSessionId(data.session_id);
              localStorage.setItem(SESSION_KEY, data.session_id);
            }
            if (data.grounding?.player_id) {
              setLastPlayer({ id: data.grounding.player_id, name: data.grounding.player_name });
            }
          }

          // Error event
          if (data.error) {
            setMessages(prev => prev.map(m =>
              m.id === botId ? { ...m, text: `❌ ${data.error}`, streaming: false } : m
            ));
          }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === botId
          ? { ...m, text: `❌ ${err.message || 'Network error'}`, streaming: false }
          : m
      ));
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, language, isRtl, lastPlayer, addMessage]);

  const handleCandidateSelect = useCallback((candidate) => {
    setLastPlayer({ id: candidate.id, name: candidate.name });
    send(`Player confirmed: ${candidate.name} (id ${candidate.id}). Please continue with the original question.`);
  }, [send]);

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const handleNewSession = () => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setLastPlayer(null);
    setMessages([{
      id: `welcome-${Date.now()}`, role: 'bot', rtl: false, ts: new Date().toISOString(),
      text: 'New conversation started. How can I help?',
      toolCalls: null, grounding: null, streaming: false,
    }]);
  };

  return (
    <div className="module" dir={isRtl ? 'rtl' : 'ltr'}>

      {/* ── Header ── */}
      <div className="module-header chat-header" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="module-icon">🤖</span>
          <div>
            <h2>
              AI Assistant{' '}
              <span style={{ fontSize: '0.65rem', fontWeight: '400', color: 'var(--text-muted)', marginLeft: '6px' }}>
                Groq · llama-3.1-8b-instant
              </span>
            </h2>
            <p>Query players, physio risk, nutrition &amp; training in natural language</p>
          </div>
        </div>

        {/* Controls: language selector + new session */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            display: 'flex', gap: '2px',
            background: 'var(--bg-card)', borderRadius: '8px',
            padding: '2px', border: '1px solid var(--border-color)',
          }}>
            {LANGUAGES.map(l => (
              <button
                key={l.code}
                onClick={() => setLanguage(l.code)}
                title={l.code === 'auto' ? 'Auto-detect language' : `Force ${l.label}`}
                style={{
                  padding: '4px 8px', fontSize: '0.72rem', borderRadius: '6px',
                  border: 'none', cursor: 'pointer', fontWeight: '600',
                  background: language === l.code ? 'var(--neon-cyan)' : 'transparent',
                  color: language === l.code ? '#000' : 'var(--text-muted)',
                  transition: 'all 0.15s',
                }}
              >
                {l.label}
              </button>
            ))}
          </div>
          <button
            onClick={handleNewSession}
            title="Start new conversation"
            style={{
              padding: '6px 10px', fontSize: '0.72rem', borderRadius: '8px',
              border: '1px solid var(--border-color)', background: 'transparent',
              color: 'var(--text-muted)', cursor: 'pointer',
            }}
          >
            ↺ New
          </button>
        </div>
      </div>

      {/* ── Quick chips ── */}
      <div style={{ padding: '8px 0 4px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {QUICK_CHIPS.map((chip, i) => (
          <button
            key={i}
            className="suggestion-chip"
            onClick={() => send(chip.message)}
            disabled={loading}
            style={{ opacity: loading ? 0.5 : 1 }}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* ── Player context badge ── */}
      {lastPlayer && (
        <div style={{
          padding: '4px 10px', fontSize: '0.72rem', color: 'var(--neon-cyan)',
          background: 'rgba(0,212,255,0.08)', borderRadius: '6px',
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          marginBottom: '4px',
        }}>
          <span>📌 Context:</span>
          <strong>{lastPlayer.name}</strong>
          <button
            onClick={() => setLastPlayer(null)}
            title="Clear player context"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.7rem' }}
          >
            ×
          </button>
        </div>
      )}

      {/* ── Chat messages ── */}
      <div className="chat-wrap">
        <div className="chat-messages">
          {messages.map((msg, i) => (
            <MessageBubble key={msg.id || i} msg={msg} onSelectCandidate={handleCandidateSelect} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input ── */}
      <div className="chat-input-row">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          rows={1}
          placeholder={isRtl ? 'اكتب سؤالك هنا…' : 'Ask about players, physio risk, nutrition…'}
          disabled={loading}
          dir={isRtl ? 'rtl' : 'ltr'}
          style={{ resize: 'none', fontFamily: 'inherit', lineHeight: '1.5', minHeight: '42px' }}
        />
        <button
          className="btn-primary"
          onClick={() => send()}
          disabled={loading || !input.trim()}
        >
          {isRtl ? '↙ إرسال' : 'Send ↗'}
        </button>
      </div>

      {/* ── Session footer ── */}
      {sessionId && (
        <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '4px', textAlign: 'center' }}>
          Session: {sessionId.substring(0, 8)}… · Lang: {language.toUpperCase()}
        </div>
      )}
    </div>
  );
}
