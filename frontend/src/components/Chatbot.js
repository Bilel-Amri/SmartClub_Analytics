import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { getAccessToken } from '../auth';

// --- Constants ---------------------------------------------------------------

const LANGUAGES = [
  { code: 'auto', label: 'Auto' },
  { code: 'en',   label: 'EN' },
  { code: 'fr',   label: 'FR' },
  { code: 'ar',   label: 'AR' },
  { code: 'tn',   label: 'TN' },
];

const QUICK_CHIPS = [
  { label: "Top risks (7 days)",    message: "Show me the top 5 players most at risk of injury in the last 7 days" },
  { label: "Top risks (30 days)",   message: "Show me the top 5 players most at risk of injury in the last 30 days" },
  { label: "ACWR trend",            message: "Show me the ACWR training load trend for the squad" },
  { label: "Nutrition plan",        message: "Generate a nutrition plan for today's training session" },
  { label: "Meal calculator",       message: "Calculate the macros for a specific meal" },
  { label: "Squad overview",        message: "Give me a full overview of the squad's current injury risk status" },
];

const RTL_LANGS = new Set(['ar', 'tn']);

const SESSION_KEY = 'smartclub_chat_session_id';

const TOOL_LABELS = {
  squad_risk:          "squad injury data",
  physio_risk:         "player risk analysis",
  player_search:       "player profile",
  physio_timeseries:   "training load history",
  nutri_generate_plan: "nutrition plan",
  nutri_meal_calc:     "meal breakdown",
  food_search:         "food database",
};

// --- Helpers -----------------------------------------------------------------

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

// --- Sub-components ----------------------------------------------------------

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
        {open ? '🔽' : '▶️'} How I answered ({toolCalls.length} tool call{toolCalls.length > 1 ? 's' : ''})
      </button>
      {open && (
        <div style={{
          marginTop: '6px', padding: '8px 12px',
          background: 'rgba(0,0,0,0.2)', borderRadius: '6px',
          fontSize: '0.72rem', color: 'var(--text-muted)',
        }}>
          {toolCalls.map((tc, i) => (
            <div key={i} style={{ marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ color: tc.ok ? '#22c55e' : '#ef4444' }}>{tc.ok ? '✅' : '❌'}</span>
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
          ) : (
            <>
              {msg.activeTool && (
                <div className="tool-status-chip">
                  <span className="tool-spinner" />
                  Fetching {TOOL_LABELS[msg.activeTool] || msg.activeTool.replace(/_/g, ' ')}...
                </div>
              )}
              {msg.text && (
                <div className="prose prose-invert max-w-none">
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                </div>
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

// --- Main Component ----------------------------------------------------------

export default function Chatbot() {
  const [messages, setMessages] = useState([{
    id: 'welcome', role: 'bot', rtl: false, ts: new Date().toISOString(),
    text: 'Hello! 👋 I\'m **SmartClub AI**.\n\nI can:\n• Predict injury risk (7d / 30d)\n• Show training load & ACWR trends\n• Retrieve nutrition plans & meal calcs\n• Search players & supplements\n\nType *help* or pick a quick action below.',
    toolCalls: null, grounding: null, streaming: false,
  }]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [toast, setToast] = useState(null);
  const [language, setLanguage] = useState('auto');
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null);
  const [lastPlayer, setLastPlayer] = useState(null);
  const bottomRef = useRef(null);

  const isRtl = RTL_LANGS.has(language);

  const TOAST_MESSAGES = {
    en: "Switched to English",
    fr: "Langue changée : Français",
    ar: "تم التبديل إلى العربية",
    tn: "بدلنا للدرجة التونسية"
  };

  const switchLanguage = (code) => {
    setLanguage(code);
    if (code !== 'auto') {
      setToast(TOAST_MESSAGES[code] || "Language changed");
      setTimeout(() => setToast(null), 2000);
    }
  };

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
    setIsStreaming(true);

    // Add an empty streaming bot message immediately
    const botId = `bot-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: botId, role: 'bot', text: '', streaming: true,
      ts: new Date().toISOString(), toolCalls: null, grounding: null, language: null, rtl: false,
    }]);

    try {
      let response = await fetch('/api/chat-llm/stream/', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}` 
        },
        body: JSON.stringify({ message: msg, session_id: sessionId, language }),
      });

      if (response.status === 401) {
        // Token might be expired. Let's force a silent refresh via an axios GET call
        // then try again.
        try {
          const { default: axios } = await import('axios');
          await axios.get('/api/auth/me/'); // This triggers the interceptor which refreshes token
          response = await fetch('/api/chat-llm/stream/', {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${getAccessToken()}` 
            },
            body: JSON.stringify({ message: msg, session_id: sessionId, language }),
          });
        } catch (e) {
          // Ignore, fallback to failing gracefully
        }
      }

      if (!response.ok) {
        await response.text();
        setMessages(prev => prev.map(m =>
          m.id === botId
            ? { ...m, text: `❌ Server error ${response.status}`, streaming: false }
            : m
        ));
        setIsStreaming(false);
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

          // Handle new unified JSON stream format from the updated agent backend
          if (data.type === 'tool_start') {
            setMessages(prev => prev.map(m => m.id === botId ? { ...m, activeTool: data.data?.tool } : m));
          } else if (data.type === 'tool_end') {
            setMessages(prev => prev.map(m => m.id === botId ? { ...m, activeTool: null } : m));
          } else if (data.type === 'text') {
            data.chunk = data.data;
          } else if (data.type === 'done') {
            data.done = true;
          } else if (data.type === 'error') {
            data.chunk = "\n\n**Error:** " + data.data;
            data.done = true; // stop stream on error
          }

          // Progressive text chunk
          if (data.chunk !== undefined) {
            fullText += data.chunk;
            setMessages(prev => prev.map(m =>
              m.id === botId ? { ...m, text: fullText } : m
            ));
          }

          // Final done event — attach metadata
          if (data.done) {
            setIsStreaming(false);
            const lang = data.language || 'en';
            setMessages(prev => prev.map(m =>
              m.id === botId
                ? { ...m, text: fullText || m.text, streaming: false, activeTool: null,
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
            setIsStreaming(false);
            setMessages(prev => prev.map(m =>
              m.id === botId ? { ...m, text: `❌ ${data.error}`, streaming: false, activeTool: null } : m
            ));
          }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === botId
          ? { ...m, text: `❌ ${err.message || 'Network error'}`, streaming: false, activeTool: null }
          : m
      ));
      setIsStreaming(false);
    } finally {
      setLoading(false);
      // setIsStreaming(false) is handled in the stream parsing, error catch, or ok-check to prevent race conditions showing it disabled momentarily too early due to wait-time.
    }
  }, [input, loading, sessionId, language, isRtl, lastPlayer, addMessage, isStreaming]);

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
    const confirmed = window.confirm("Start a new conversation? This will clear the current chat history.");
    if (confirmed) {
      localStorage.removeItem(SESSION_KEY);
      setSessionId(null);
      setLastPlayer(null);
      setMessages([{
        id: `welcome-${Date.now()}`, role: 'bot', rtl: false, ts: new Date().toISOString(),
        text: 'New conversation started. How can I help?',
        toolCalls: null, grounding: null, streaming: false,
      }]);
    }
  };

  return (
    <div className="module" dir={isRtl ? 'rtl' : 'ltr'}>
      {toast && (
        <div className="lang-toast">{toast}</div>
      )}

      {/* -- Header -- */}
      <div className="module-header chat-header" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="module-icon">💬</span>
          <div>
            <h2>
              AI Assistant{' '}
              <span style={{ fontSize: '0.65rem', fontWeight: '400', color: 'var(--text-muted)', marginLeft: '6px' }}>
                AI Data Intelligence
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
                onClick={() => switchLanguage(l.code)}
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
            ➕ New
          </button>
        </div>
      </div>

      {/* -- Quick chips -- */}
      <div style={{ padding: '8px 0 4px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {QUICK_CHIPS.map((chip, i) => (
          <button
            key={i}
            className="suggestion-chip"
            onClick={() => send(chip.message)}
            disabled={loading || isStreaming}
            style={{ opacity: (loading || isStreaming) ? 0.5 : 1 }}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* -- Player context badge -- */}
      {lastPlayer && (
        <div style={{
          padding: '4px 10px', fontSize: '0.72rem', color: 'var(--neon-cyan)',
          background: 'rgba(0,212,255,0.08)', borderRadius: '6px',
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          marginBottom: '4px',
        }}>
          <span>🧠 Context:</span>
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

      {/* -- Chat messages -- */}
      <div className="chat-wrap">
        <div className="chat-messages">
          {messages.map((msg, i) => (
            <MessageBubble key={msg.id || i} msg={msg} onSelectCandidate={handleCandidateSelect} />
          ))}
          
          {isStreaming && (
            <div className="flex items-start gap-3 mb-4" style={{ paddingLeft: '16px' }}>
              <div className="bot-avatar" style={{ marginRight: '8px' }}>🤖</div>
              <div className="typing-indicator" style={{ display: 'flex', alignItems: 'center' }}>
                <span></span><span></span><span></span>
              </div>
            </div>
          )}
          
          <div ref={bottomRef} />
        </div>
      </div>

      {/* -- Input -- */}
      <div className="chat-input-row">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          rows={1}
          placeholder={isRtl ? '➤ إسأل هنا…' : 'Ask about players, physio risk, nutrition…'}
          disabled={loading || isStreaming}
          dir={isRtl ? 'rtl' : 'ltr'}
          style={{ resize: 'none', fontFamily: 'inherit', lineHeight: '1.5', minHeight: '42px' }}
        />
        <button
          className="btn-primary"
          onClick={() => send()}
          disabled={loading || isStreaming || !input.trim()}
        >
          {isRtl ? '➤ أرسل' : 'Send 🚀'}
        </button>
      </div>

      {/* -- Session footer -- */}
      {sessionId && (
        <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '4px', textAlign: 'center' }}>
          Session: {sessionId.substring(0, 8)}… · Lang: {language.toUpperCase()}
        </div>
      )}
    </div>
  );
}