from __future__ import annotations

import json
import logging
import os
import time
from typing import Generator, Iterator

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Provider detection
# ──────────────────────────────────────────────

LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "groq").lower()      # "groq" | "openai"
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

FALLBACK_PROVIDER = os.getenv("FALLBACK_PROVIDER", "").lower()
FALLBACK_MODEL    = os.getenv("FALLBACK_MODEL", "")

# Groq's free-tier rate limits (requests per minute / tokens per minute)
GROQ_RPM_LIMIT = 30
GROQ_TPM_LIMIT = 14_400   # llama-3.1-8b-instant free tier

# ──────────────────────────────────────────────
# Lazy client initialisation
# ──────────────────────────────────────────────

_groq_client   = None
_openai_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            import httpx
            _groq_client = Groq(
                api_key=GROQ_API_KEY,
                http_client=httpx.Client(
                    timeout=httpx.Timeout(15.0, connect=5.0),
                    limits=httpx.Limits(
                        max_keepalive_connections=5,
                        max_connections=10,
                        keepalive_expiry=30,
                    ),
                ),
            )
        except ImportError:
            raise RuntimeError(
                "groq package not installed. Run: pip install groq"
            )
    return _groq_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=OPENAI_API_KEY)
        except ImportError:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai"
            )
    return _openai_client


# ──────────────────────────────────────────────
# Core chat completion  (non-streaming)
# ──────────────────────────────────────────────

def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    provider: str | None = None,
    model: str | None = None,
    _retry: int = 0,
) -> dict:
    """
    Returns the raw API response dict (normalised to OpenAI schema).
    Raises LLMError on unrecoverable failure.
    """
    provider = provider or LLM_PROVIDER
    model    = model    or LLM_MODEL

    try:
        if provider == "groq":
            return _groq_chat(messages, tools, temperature, max_tokens, model)
        elif provider == "openai":
            return _openai_chat(messages, tools, temperature, max_tokens, model)
        else:
            raise LLMError(f"Unknown LLM_PROVIDER: '{provider}'")

    except RateLimitError as exc:
        if _retry < 3:
            wait = min(2 ** _retry, 8)          # exponential back-off: 1s, 2s, 4s (max 8)
            logger.warning("Rate limit hit, retrying in %ss…", wait)
            time.sleep(wait)
            return chat_completion(
                messages, tools, temperature, max_tokens,
                provider, model, _retry=_retry + 1
            )
        # Try fallback provider before giving up
        if FALLBACK_PROVIDER and _retry == 3:
            logger.warning("Switching to fallback provider: %s", FALLBACK_PROVIDER)
            return chat_completion(
                messages, tools, temperature, max_tokens,
                provider=FALLBACK_PROVIDER,
                model=FALLBACK_MODEL or model,
                _retry=0,
            )
        raise LLMError(f"Rate limit exhausted after retries: {exc}") from exc

    except Exception as exc:
        logger.exception("LLM call failed: %s", exc)
        raise LLMError(str(exc)) from exc


# ──────────────────────────────────────────────
# Streaming completion  (yields text chunks)
# ──────────────────────────────────────────────

def chat_completion_stream(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    provider: str | None = None,
    model: str | None = None,
) -> Generator[str, None, None]:
    """
    Yields SSE-formatted strings: "data: <chunk>\\n\\n"
    Last event is always:         "data: [DONE]\\n\\n"

    Tool calls are NOT streamed — if a tool_call is detected in the
    accumulated delta, the generator yields a special JSON sentinel:
        "data: __TOOL_CALL__:<json>\\n\\n"
    so views.py can intercept and execute the tool.
    """
    provider = provider or LLM_PROVIDER
    model    = model    or LLM_MODEL

    try:
        if provider == "groq":
            yield from _groq_stream(messages, tools, temperature, max_tokens, model)
        elif provider == "openai":
            yield from _openai_stream(messages, tools, temperature, max_tokens, model)
        else:
            raise LLMError(f"Unknown LLM_PROVIDER: '{provider}'")
    except Exception as exc:
        logger.exception("Streaming failed: %s", exc)
        yield f"data: __ERROR__:{exc}\n\n"


# ──────────────────────────────────────────────
# Groq implementations
# ──────────────────────────────────────────────

def _groq_chat(messages, tools, temperature, max_tokens, model) -> dict:
    client = _get_groq_client()
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        response = client.chat.completions.create(**kwargs, timeout=15.0)
    except Exception as exc:
        _classify_and_raise(exc)

    # Normalise to a plain dict (same shape as OpenAI response)
    return _normalise_groq_response(response)


def _groq_stream(messages, tools, temperature, max_tokens, model) -> Iterator[str]:
    client = _get_groq_client()
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    # NOTE: Groq supports tool_calls in streaming but the accumulation is manual.
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    accumulated_tool_calls: dict = {}   # index -> {id, name, arguments}

    try:
        stream = client.chat.completions.create(**kwargs, timeout=15.0)
    except Exception as exc:
        _classify_and_raise(exc)

    try:
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            # ── Text chunk ──────────────────────────────
            if delta.content:
                yield f"data: {json.dumps({'text': delta.content})}\n\n"

            # ── Tool call accumulation ───────────────────
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id":        tc.id or "",
                            "name":      tc.function.name if tc.function else "",
                            "arguments": "",
                        }
                    if tc.function:
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function.name:
                            accumulated_tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

            finish = chunk.choices[0].finish_reason if chunk.choices else None
            if finish in ("tool_calls", "stop") and accumulated_tool_calls:
                for call in accumulated_tool_calls.values():
                    yield f"data: __TOOL_CALL__:{json.dumps(call)}\n\n"
                accumulated_tool_calls = {}

        yield "data: [DONE]\n\n"
    except Exception as exc:
        err_msg = str(exc)
        if "failed_generation" in err_msg or "Failed to call a function" in err_msg:
            # Prompt too complex for function calling
            # Yield a clear error and stop
            yield f"data: {json.dumps({'type': 'error', 'data': 'The request was too complex. Please try rephrasing.'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        else:
            _classify_and_raise(exc)


# ──────────────────────────────────────────────
# OpenAI implementations  (fallback / alternative)
# ──────────────────────────────────────────────

def _openai_chat(messages, tools, temperature, max_tokens, model) -> dict:
    client = _get_openai_client()
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        _classify_and_raise(exc)

    return response.model_dump()


def _openai_stream(messages, tools, temperature, max_tokens, model) -> Iterator[str]:
    client = _get_openai_client()
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    accumulated_tool_calls: dict = {}

    try:
        stream = client.chat.completions.create(**kwargs)
    except Exception as exc:
        _classify_and_raise(exc)

    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue

        if delta.content:
            yield f"data: {json.dumps({'text': delta.content})}\n\n"

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in accumulated_tool_calls:
                    accumulated_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                if tc.id:
                    accumulated_tool_calls[idx]["id"] = tc.id
                if tc.function and tc.function.name:
                    accumulated_tool_calls[idx]["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

        finish = chunk.choices[0].finish_reason if chunk.choices else None
        if finish in ("tool_calls", "stop") and accumulated_tool_calls:
            for call in accumulated_tool_calls.values():
                yield f"data: __TOOL_CALL__:{json.dumps(call)}\n\n"
            accumulated_tool_calls = {}

    yield "data: [DONE]\n\n"


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _normalise_groq_response(response) -> dict:
    """Convert Groq SDK object to plain dict matching OpenAI schema."""
    choices = []
    for choice in response.choices:
        msg = choice.message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "id":       tc.id,
                    "type":     "function",
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        choices.append({
            "index": choice.index,
            "message": {
                "role":       msg.role,
                "content":    msg.content,
                "tool_calls": tool_calls,
            },
            "finish_reason": choice.finish_reason,
        })

    return {
        "id":      response.id,
        "model":   response.model,
        "choices": choices,
        "usage": {
            "prompt_tokens":     response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens":      response.usage.total_tokens,
        } if response.usage else {},
    }


def _classify_and_raise(exc: Exception):
    """Map provider SDK exceptions to our own typed errors."""
    msg = str(exc).lower()
    if "rate limit" in msg or "429" in msg:
        import time
        print(f"=== RATE LIMIT HIT at {time.strftime('%H:%M:%S')} ===")
        raise RateLimitError(str(exc)) from exc
    if "auth" in msg or "401" in msg or "api key" in msg:
        raise AuthError(str(exc)) from exc
    raise LLMError(str(exc)) from exc


# ──────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────

class LLMError(Exception):
    """Generic LLM failure."""

class RateLimitError(LLMError):
    """Provider rate-limit hit."""

class AuthError(LLMError):
    """Bad API key or permissions."""