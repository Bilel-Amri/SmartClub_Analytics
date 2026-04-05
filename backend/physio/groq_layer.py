from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict

SYSTEM_PROMPT = (
    "You are SmartClub PhysioAI assistant. Give concise, clinical, non-alarmist guidance. "
    "Never invent metrics not present in input. Mention uncertainty when confidence is low. "
    "Output plain text only."
)

PROMPT_TEMPLATES = {
    "squad_daily_risk": (
        "Summarize this player daily risk card for a head coach. "
        "Input: {payload}. Return 4-6 lines with risk reason, session decision, monitoring, escalation."
    ),
    "player_risk_simulator": (
        "Explain this simulated profile risk in practical terms. "
        "Input: {payload}. Return risk interpretation, key drivers, and immediate training decision."
    ),
    "absence_prediction": (
        "Explain this absence prediction to staff. "
        "Input: {payload}. Return expected range, confidence, and first 48h action priorities."
    ),
}


FALLBACK_TEXT = {
    "squad_daily_risk": (
        "Risk is elevated by injury history and current load context. "
        "Reduce max-speed exposure today, run targeted physio checks before training, "
        "and escalate if discomfort appears during session."
    ),
    "player_risk_simulator": (
        "This profile is sensitive to cumulative injury burden and recovery timing. "
        "Use a controlled training block with daily RPE and soreness checks before increasing intensity."
    ),
    "absence_prediction": (
        "The current pattern suggests a meaningful recurrence scenario. "
        "Prioritize imaging and objective clinical testing before full-speed return progression."
    ),
}


def _call_groq(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("missing_groq_key")

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 380,
    }

    req = urllib.request.Request(
        url="https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "SmartClub-Analytics/1.0"
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def generate_explanation(function_type: str, payload: Dict) -> dict:
    function_type = (function_type or "").strip()
    if function_type not in PROMPT_TEMPLATES:
        function_type = "player_risk_simulator"

    prompt = PROMPT_TEMPLATES[function_type].format(payload=json.dumps(payload, ensure_ascii=True))

    try:
        text = _call_groq(SYSTEM_PROMPT, prompt)
        return {"text": text, "provider": "groq", "fallback_used": False}
    except Exception:
        return {
            "text": FALLBACK_TEXT[function_type],
            "provider": "fallback",
            "fallback_used": True,
        }
