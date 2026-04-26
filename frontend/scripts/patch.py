import codecs

path = 'c:/Users/bilel/Downloads/SmartClub_Analytics-main/frontend/src/components/Chatbot.js'
with codecs.open(path, 'r', 'utf-8') as f:
    text = f.read()

# Fix 1: UTF-8 encoding is handled by saving with 'utf-8'. Fix emojis:
text = text.replace("'Hello! ?? I\\'m", "'Hello! 👋 I\\'m")
text = text.replace("<span className=\"module-icon\">??</span>", "<span className=\"module-icon\">💬</span>")
text = text.replace("<span>?? Context:</span>", "<span>🧠 Context:</span>")
text = text.replace("{isRtl ? '? ?????' : 'Send ?'}", "{isRtl ? '➤ أرسل' : 'Send 🚀'}")
text = text.replace("{isUser && <div className=\"user-avatar\">??</div>}", "{isUser && <div className=\"user-avatar\">👤</div>}")
text = text.replace("{!isUser && <div className=\"bot-avatar\">??</div>}", "{!isUser && <div className=\"bot-avatar\">🤖</div>}")
text = text.replace("{tc.ok ? '?' : '?'}", "{tc.ok ? '✅' : '❌'}")
text = text.replace("{open ? '?' : '?'} How I answered", "{open ? '🔽' : '▶️'} How I answered")
text = text.replace("? New", "➕ New")
text = text.replace("? Server error", "❌ Server error")
text = text.replace("? ${data.error}", "❌ ${data.error}")
text = text.replace("? ${err.message", "❌ ${err.message")

# Fix 2 & Fix 5
MB_OLD = """          {isUser ? (
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
          )}"""

MB_NEW = """          {isUser ? (
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
          )}"""
text = text.replace(MB_OLD, MB_NEW)

TL_ADD = """const SESSION_KEY = 'smartclub_chat_session_id';

const TOOL_LABELS = {
  squad_risk:          "squad injury data",
  physio_risk:         "player risk analysis",
  player_search:       "player profile",
  physio_timeseries:   "training load history",
  nutri_generate_plan: "nutrition plan",
  nutri_meal_calc:     "meal breakdown",
  food_search:         "food database",
};"""
text = text.replace("const SESSION_KEY = 'smartclub_chat_session_id';", TL_ADD)

STATE_OLD = """  const [loading, setLoading] = useState(false);
  const [language, setLanguage] = useState('auto');
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null);"""

STATE_NEW = """  const [loading, setLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [toast, setToast] = useState(null);
  const [language, setLanguage] = useState('auto');
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || null);"""
text = text.replace(STATE_OLD, STATE_NEW)

LANG_OLD_CLICK = "onClick={() => setLanguage(l.code)}"
LANG_NEW_CLICK = """onClick={() => switchLanguage(l.code)}"""
text = text.replace(LANG_OLD_CLICK, LANG_NEW_CLICK)

HELP_OLD = """  const isRtl = RTL_LANGS.has(language);"""
HELP_NEW = """  const isRtl = RTL_LANGS.has(language);

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
  };"""
text = text.replace(HELP_OLD, HELP_NEW)

TYPING_REND = """      </div>

      {/* -- Input -- */}"""
TYPING_REND_NEW = """      </div>

      {isStreaming && (
        <div className="flex items-start gap-3 mb-4" style={{ paddingLeft: '16px' }}>
          <div className="bot-avatar" style={{ marginRight: '8px' }}>🤖</div>
          <div className="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      )}

      {/* -- Input -- */}"""
text = text.replace(TYPING_REND, TYPING_REND_NEW)

text = text.replace("disabled={loading || !input.trim()}", "disabled={loading || isStreaming || !input.trim()}")
text = text.replace("disabled={loading}", "disabled={loading || isStreaming}")
text = text.replace("style={{ opacity: loading ? 0.5 : 1 }}", "style={{ opacity: (loading || isStreaming) ? 0.5 : 1 }}")

SEND_OLD = """    setLoading(true);

    // Add an empty streaming bot message immediately"""
SEND_NEW = """    setLoading(true);
    setIsStreaming(true);

    // Add an empty streaming bot message immediately"""
text = text.replace(SEND_OLD, SEND_NEW)

STREAM_CATCH_OLD = """    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, language, isRtl, lastPlayer, addMessage]);"""
STREAM_CATCH_NEW = """    } finally {
      setLoading(false);
      setIsStreaming(false);
    }
  }, [input, loading, sessionId, language, isRtl, lastPlayer, addMessage]);"""
text = text.replace(STREAM_CATCH_OLD, STREAM_CATCH_NEW)

DONE_OLD = """// Final done event — attach metadata
          if (data.done) {"""
DONE_NEW = """// Final done event — attach metadata
          if (data.done) {
            setIsStreaming(false);"""
text = text.replace(DONE_OLD, DONE_NEW)

ERROR_OLD = """// Error event
          if (data.error) {"""
ERROR_NEW = """// Error event
          if (data.error) {
            setIsStreaming(false);"""
text = text.replace(ERROR_OLD, ERROR_NEW)

DATA_HAND_OLD = """// Handle new unified JSON stream format from the updated agent backend"""
DATA_HAND_NEW = """// Handle new unified JSON stream format from the updated agent backend
          if (data.type === 'tool_start') {
            setMessages(prev => prev.map(m => m.id === botId ? { ...m, activeTool: data.data?.tool } : m));
          } else if (data.type === 'tool_end') {
            setMessages(prev => prev.map(m => m.id === botId ? { ...m, activeTool: null } : m));
          }
"""
text = text.replace(DATA_HAND_OLD, DATA_HAND_NEW)

NEW_CHAT_OLD = """  const handleNewSession = () => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setLastPlayer(null);
    setMessages([{
      id: `welcome-${Date.now()}`, role: 'bot', rtl: false, ts: new Date().toISOString(),
      text: 'New conversation started. How can I help?',
      toolCalls: null, grounding: null, streaming: false,
    }]);
  };"""
NEW_CHAT_NEW = """  const handleNewSession = () => {
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
  };"""
text = text.replace(NEW_CHAT_OLD, NEW_CHAT_NEW)

TOAST_REND = """    <div className="module" dir={isRtl ? 'rtl' : 'ltr'}>

      {/* -- Header -- */}"""
TOAST_REND_NEW = """    <div className="module" dir={isRtl ? 'rtl' : 'ltr'}>
      {toast && (
        <div className="lang-toast">{toast}</div>
      )}

      {/* -- Header -- */}"""
text = text.replace(TOAST_REND, TOAST_REND_NEW)

with codecs.open(path, 'w', 'utf-8') as f:
    f.write(text)

print("ALL PATCHES APPLIED!")