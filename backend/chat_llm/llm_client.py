"""
LLM client — providers: groq (default), openai, openrouter, ollama (fallback).
Public API:
  chat_completion(messages, tools=None, temperature=0.3)          → _Message
  chat_completion_stream(messages, temperature=0.3)               → generator[str]
"""
from __future__ import annotations
import json
import os
from django.conf import settings

MAX_TOKENS = 600  # enough for a rich reply with risk table + action


def _get_setting(name: str, default: str = '') -> str:
    return getattr(settings, name, os.getenv(name, default))


# ── Shared response objects ────────────────────────────────────────────────────

class _ToolCall:
    def __init__(self, tc: dict):
        self.id = tc.get('id', '')
        class _Fn:
            def __init__(self, f: dict):
                self.name = f.get('name', '')
                args = f.get('arguments', '{}')
                self.arguments = args if isinstance(args, str) else json.dumps(args)
        self.function = _Fn(tc.get('function', {}))


class _Message:
    def __init__(self, m: dict):
        self.role       = m.get('role', 'assistant')
        self.content    = m.get('content') or ''
        raw_tc          = m.get('tool_calls') or []
        self.tool_calls = [_ToolCall(tc) for tc in raw_tc] if raw_tc else []

    def model_dump(self) -> dict:
        tcs = []
        for tc in self.tool_calls:
            tcs.append({
                'id': tc.id,
                'type': 'function',
                'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
            })
        return {'role': self.role, 'content': self.content, 'tool_calls': tcs or None}


def _wrap_sdk_message(sdk_msg) -> _Message:
    """Convert an openai SDK message object into our _Message shape."""
    tcs = []
    for tc in (sdk_msg.tool_calls or []):
        tcs.append({'id': tc.id, 'function': {'name': tc.function.name,
                                               'arguments': tc.function.arguments}})
    return _Message({'role': getattr(sdk_msg, 'role', 'assistant'),
                     'content': sdk_msg.content or '', 'tool_calls': tcs})


# ── Ollama (local, requests-based) ────────────────────────────────────────────

def _ollama_chat(model: str, messages: list[dict], tools: list[dict] | None,
                 temperature: float, stream: bool = False):
    import requests
    base = _get_setting('OLLAMA_BASE_URL', 'http://localhost:11434')
    url  = f'{base.rstrip("/")}/v1/chat/completions'
    payload: dict = {
        'model': model, 'messages': messages,
        'temperature': temperature, 'max_tokens': MAX_TOKENS, 'stream': stream,
    }
    if tools:
        payload['tools'] = tools
        payload['tool_choice'] = 'auto'
    try:
        if stream:
            resp = requests.post(url, json=payload, timeout=180, stream=True)
            resp.raise_for_status()
            def _gen():
                for line in resp.iter_lines():
                    if not line:
                        continue
                    s = line.decode('utf-8') if isinstance(line, bytes) else line
                    if s.startswith('data:'):
                        s = s[5:].strip()
                    if s == '[DONE]':
                        break
                    try:
                        delta = json.loads(s)['choices'][0].get('delta', {})
                        chunk = delta.get('content') or ''
                        if chunk:
                            yield chunk
                    except Exception:
                        continue
            return _gen()
        else:
            resp = requests.post(url, json=payload, timeout=180)
            resp.raise_for_status()
            return _Message(resp.json()['choices'][0]['message'])
    except requests.exceptions.ConnectionError:
        raise RuntimeError('Cannot connect to Ollama — run: ollama serve')
    except requests.exceptions.Timeout:
        raise RuntimeError('Ollama timed out')
    except requests.exceptions.HTTPError as e:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text[:300]
        raise RuntimeError(f'Ollama {resp.status_code}: {detail}') from e


# ── SDK-based providers (groq, openai, openrouter) ────────────────────────────

def _make_sdk_client():
    provider = _get_setting('LLM_PROVIDER', 'groq').lower()
    try:
        from openai import OpenAI
    except ImportError:
        return None, None, 'openai package not installed — run: pip install openai'

    if provider == 'groq':
        key = _get_setting('GROQ_API_KEY', '')
        if not key:
            return None, None, 'GROQ_API_KEY not set in .env — get free key: https://console.groq.com'
        model = _get_setting('LLM_MODEL', 'llama-3.1-8b-instant')
        return OpenAI(api_key=key, base_url='https://api.groq.com/openai/v1',
                      timeout=30.0), model, None

    if provider == 'openai':
        key = _get_setting('OPENAI_API_KEY', '')
        if not key:
            return None, None, 'OPENAI_API_KEY not set in .env'
        return OpenAI(api_key=key), _get_setting('LLM_MODEL', 'gpt-4o-mini'), None

    if provider == 'openrouter':
        key = _get_setting('OPENROUTER_API_KEY', '')
        if not key:
            return None, None, 'OPENROUTER_API_KEY not set in .env'
        client = OpenAI(api_key=key, base_url='https://openrouter.ai/api/v1')
        return client, _get_setting('LLM_MODEL', 'openai/gpt-4o-mini'), None

    return None, None, f'Unknown LLM_PROVIDER: {provider}'


# Lazy singleton — reset when settings change
_sdk_client = _sdk_model = _sdk_error = None
_sdk_loaded = False
_sdk_loaded_provider = None  # track which provider the singleton was built for


def _get_sdk_client():
    global _sdk_client, _sdk_model, _sdk_error, _sdk_loaded, _sdk_loaded_provider
    provider = _get_setting('LLM_PROVIDER', 'groq').lower()
    # Rebuild if provider changed (e.g. after restart / settings reload)
    if not _sdk_loaded or _sdk_loaded_provider != provider:
        _sdk_client, _sdk_model, _sdk_error = _make_sdk_client()
        _sdk_loaded = True
        _sdk_loaded_provider = provider
        import logging
        log = logging.getLogger('chat_llm')
        if _sdk_error:
            log.warning('LLM client error: %s', _sdk_error)
        else:
            log.info('LLM client ready: provider=%s model=%s', provider, _sdk_model)
    return _sdk_client, _sdk_model, _sdk_error


def _sdk_call(stream: bool, messages: list[dict], tools: list[dict] | None,
              temperature: float):
    client, model, error = _get_sdk_client()
    if error:
        raise RuntimeError(error)
    kwargs: dict = dict(model=model, messages=messages,
                        temperature=temperature, max_tokens=MAX_TOKENS)
    if tools:
        kwargs['tools'] = tools
        kwargs['tool_choice'] = 'auto'
    if stream:
        kwargs['stream'] = True
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    if stream:
        def _gen():
            for chunk in resp:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        return _gen()
    return _wrap_sdk_message(resp.choices[0].message)


# ── Fallback helper ────────────────────────────────────────────────────────────

def _with_fallback(primary_fn, fallback_fn):
    try:
        return primary_fn()
    except RuntimeError:
        return fallback_fn()


# ── Public API ────────────────────────────────────────────────────────────────

def chat_completion(messages: list[dict], tools: list[dict] | None = None,
                    temperature: float = 0.3, language: str = '') -> '_Message':
    """
    Non-streaming completion. Returns _Message with .content, .tool_calls,
    and .model_dump(). Raises RuntimeError on unrecoverable failure.
    """
    provider  = _get_setting('LLM_PROVIDER', 'groq').lower()
    fallback  = _get_setting('FALLBACK_PROVIDER', '').lower()
    fb_model  = _get_setting('FALLBACK_MODEL', '') or 'qwen2.5:3b'

    def _primary():
        if provider == 'ollama':
            return _ollama_chat(_get_setting('LLM_MODEL', 'llama-3.1-8b-instant'),
                                messages, tools, temperature)
        return _sdk_call(stream=False, messages=messages, tools=tools,
                         temperature=temperature)

    def _fallback():
        if fallback == 'ollama':
            return _ollama_chat(fb_model, messages, tools, temperature)
        raise RuntimeError('No fallback provider configured')

    if fallback:
        return _with_fallback(_primary, _fallback)
    return _primary()


def chat_completion_stream(messages: list[dict],
                           temperature: float = 0.3):
    """
    Streaming completion (no tool schemas — final-answer pass only).
    Returns a generator of str text chunks.
    Falls back gracefully if the provider doesn't support streaming.
    """
    provider = _get_setting('LLM_PROVIDER', 'groq').lower()
    fallback = _get_setting('FALLBACK_PROVIDER', '').lower()
    fb_model = _get_setting('FALLBACK_MODEL', '') or 'qwen2.5:3b'

    def _primary():
        if provider == 'ollama':
            return _ollama_chat(_get_setting('LLM_MODEL', 'llama-3.1-8b-instant'),
                                messages, None, temperature, stream=True)
        return _sdk_call(stream=True, messages=messages, tools=None,
                         temperature=temperature)

    def _fallback_gen():
        if fallback == 'ollama':
            return _ollama_chat(fb_model, messages, None, temperature, stream=True)
        # Last resort: non-stream, yield single chunk
        msg = chat_completion(messages, temperature=temperature)
        def _once():
            yield msg.content
        return _once()

    try:
        return _primary()
    except RuntimeError:
        if fallback:
            return _fallback_gen()
        raise
