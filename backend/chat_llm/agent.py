from __future__ import annotations

import json
import logging
import re
from typing import Any

from .llm_client import chat_completion, chat_completion_stream, LLMError
from .tools import TOOL_SCHEMAS, execute_tool
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Token budget (conservative for free tier)
# ──────────────────────────────────────────────
MAX_HISTORY_TOKENS = 1500    # total history sent per request
MAX_RESPONSE_TOKENS = 400     # max LLM output tokens
APPROX_CHARS_PER_TOKEN = 4    # rough estimator (good enough)

# ──────────────────────────────────────────────
# System prompts  (per language)
# ──────────────────────────────────────────────

SYSTEM_PROMPTS: dict[str, str] = {
    "en": (
        "You are SmartClub AI, a football club data assistant. "
        "NEVER answer from memory — always call a tool first. "
        "TOOL RULES: "
        "'list/show/all players/squad' → list_all_players. "
        "'squad injury/risk' → squad_risk. "
        "'[player name] injury/risk' → player_search then physio_risk(exact id from search). "
        "'[player name] training/ACWR' → player_search then physio_timeseries(exact id). "
        "'[player name] nutrition' → player_search then nutri_generate_plan(exact id). "
        "'food/meal calc' → nutri_meal_calc or food_search. "
        "CRITICAL: after player_search, use ONLY the returned player_id. Never guess IDs. "
        "ERROR RULE: if tool returns error:true → say only: ⚠️ Service unavailable. "
        "If tool returns data → present ALL data, never say 'service unavailable'. "
        "GREETING RULE: pure greeting (hi/hello only) → say: "
        "Hey! I'm SmartClub AI 📊 I help with: injury risk, training load, nutrition, player search. "
        "Greeting + request → skip greeting, call tool directly. "
        "Off-topic → say: I only help with injury risk, training load, nutrition, player search. "
        "FORMAT: player list → one line each: #8 Ellyes Skhiri — Defensive Mid — Age 29 — Available. "
        "Single player: show ALL available fields from tool data like this: "
        "**Ellyes Skhiri** | Jersey #8 | Defensive Mid | Age: 29 | Tunisian | Available "
        "Height: 183cm | Weight: 78kg | Foot: Right "
        "Only include a field if the tool returned a non-null value for it. "
        "Never write Xcm or Xkg — if height/weight are missing just omit those lines. "
        "Risk data → Risk Score: X.XX — LEVEL | ACWR: X.XX | Fatigue: X.XX | Recommendation: text. "
        "Never show player_id, _mock, or raw JSON fields. Never repeat a player twice. "
        "Never print empty fields. Use Markdown. Respond in English."
    ),
    "fr": (
        "Tu es SmartClub AI, assistant data football. "
        "Ne réponds JAMAIS de mémoire — appelle toujours un outil d'abord. "
        "RÈGLES OUTILS: "
        "'liste/tous joueurs/équipe' → list_all_players. "
        "'risque blessure équipe' → squad_risk. "
        "'[nom joueur] risque/blessure' → player_search puis physio_risk(id exact). "
        "'[nom joueur] charge/ACWR' → player_search puis physio_timeseries(id exact). "
        "'[nom joueur] nutrition' → player_search puis nutri_generate_plan(id exact). "
        "'repas/aliment' → nutri_meal_calc ou food_search. "
        "CRITIQUE: après player_search, utilise UNIQUEMENT le player_id retourné. "
        "ERREUR: si outil retourne error:true → dis seulement: ⚠️ Service indisponible. "
        "Si outil retourne des données → présente TOUTES les données. "
        "SALUTATION pure → dis: Salut! Je suis SmartClub AI 📊 "
        "Salutation + demande → ignore salutation, appelle l'outil directement. "
        "Hors-sujet → dis: J'aide uniquement avec risque blessure, charge, nutrition, joueurs. "
        "FORMAT: liste → #8 Ellyes Skhiri — Milieu Déf — 29 ans — Disponible. "
        "Joueur seul: montre TOUS les champs disponibles comme ceci: "
        "**Ellyes Skhiri** | Maillot #8 | Milieu Déf | Âge: 29 | Tunisien | Disponible "
        "Taille: 183cm | Poids: 78kg | Pied: Droit "
        "N'inclus un champ que s'il n'est pas nul. "
        "N'écris jamais Xcm ou Xkg — si la taille/poids manquent, omet ces lignes. "
        "Risque → Score: X.XX — NIVEAU | ACWR: X.XX | Fatigue: X.XX | Recommandation: texte. "
        "Jamais player_id, _mock ou JSON brut. Jamais répéter un joueur. Markdown. Français."
    ),
    "ar": (
        "أنت SmartClub AI، مساعد بيانات كرة القدم. "
        "لا تجب من الذاكرة أبداً — استدعِ أداة دائماً. "
        "قواعد الأدوات: "
        "'قائمة/كل اللاعبين/الفريق' → list_all_players. "
        "'خطر إصابة الفريق' → squad_risk. "
        "'[اسم لاعب] خطر/إصابة' → player_search ثم physio_risk(id من البحث). "
        "'[اسم لاعب] تدريب/ACWR' → player_search ثم physio_timeseries(id من البحث). "
        "'[اسم لاعب] تغذية' → player_search ثم nutri_generate_plan(id من البحث). "
        "'وجبة/طعام' → nutri_meal_calc أو food_search. "
        "مهم: بعد player_search استخدم player_id المُرجَع فقط. لا تخمن. "
        "خطأ: إذا أعادت الأداة error:true → قل فقط: ⚠️ الخدمة غير متاحة. "
        "إذا أعادت بيانات → اعرض كل البيانات. "
        "تحية فقط → قل: مرحباً! أنا SmartClub AI 📊 "
        "تحية + طلب → تجاهل التحية واستدعِ الأداة مباشرة. "
        "خارج الموضوع → أنا أساعد فقط في: خطر إصابة، تدريب، تغذية، بحث لاعبين. "
        "تنسيق: قائمة → #8 إلياس سخيري — وسط دفاعي — 29 سنة — متاح. "
        "لاعب واحد: اعرض جميع الحقول المتاحة من البيانات مثل هذا: "
        "**إلياس سخيري** | رقم 8 | وسط دفاعي | العمر: 29 | تونسي | متاح "
        "الطول: 183cm | الوزن: 78kg | القدم: اليمنى "
        "قم بتضمين الحقل فقط إذا كان له قيمة. "
        "لا تكتب أبداً Xcm أو Xkg — إذا كان الطول/الوزن مفقوداً، تجاهل تلك الأسطر. "
        "خطر → النتيجة: X.XX — المستوى | ACWR: X.XX | إجهاد: X.XX | توصية: نص. "
        "لا تعرض player_id أو _mock. لا تكرر لاعباً. استخدم Markdown. بالعربية."
    ),
    "tn": (
        "أنت SmartClub AI، مساعد داتا كرة القدم. "
        "ما تجاوبش من الذاكرة — شغل أداة دائماً. "
        "قواعد الأدوات: "
        "'قائمة/كل اللاعبين/الفريق' → list_all_players. "
        "'خطر إصابة الفريق' → squad_risk. "
        "'[اسم لاعب] خطر/إصابة' → player_search وبعدها physio_risk(id من البحث). "
        "'[اسم لاعب] تدريب/ACWR' → player_search وبعدها physio_timeseries(id من البحث). "
        "'[اسم لاعب] تغذية' → player_search وبعدها nutri_generate_plan(id من البحث). "
        "'ماكلة/أكل' → nutri_meal_calc ولا food_search. "
        "مهم: بعد player_search استخدم player_id اللي رجع بالضبط. ما تخمنش. "
        "خطأ: كي الأداة ترجع error:true → قول بس: ⚠️ الخدمة مش متاحة. "
        "كي الأداة ترجع داتا → عرض كل الداتا. "
        "سلام بس → قول: أهلا! أنا SmartClub AI 📊 "
        "سلام + طلب → تجاهل السلام وشغل الأداة على طول. "
        "خارج الموضوع → أنا نساعد بس في: خطر إصابة، تدريب، تغذية، بحث لاعبين. "
        "تنسيق: قائمة → #8 إلياس سخيري — وسط دفاعي — 29 سنة — متاح. "
        "لاعب واحد: عرض كل البيانات المتاحة كيما هكا: "
        "**إلياس سخيري** | رقم 8 | وسط دفاعي | العمر: 29 | تونسي | متاح "
        "الطول: 183cm | الوزن: 78kg | القدم: اليمنى "
        "حط الحقل كان فيه قيمة برك. "
        "عمرك ما تكتب Xcm ولا Xkg — كان الطول/الوزن ناقصين، نحي الأسطر هذيكا. "
        "خطر → النتيجة: X.XX — المستوى | ACWR: X.XX | إجهاد: X.XX | توصية: نص. "
        "ما تعرضش player_id ولا _mock. ما تكررش لاعب. استخدم Markdown. بالدرجة."
    ),
}

# ──────────────────────────────────────────
# Context / history trimming
# ──────────────────────────────────────────
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // APPROX_CHARS_PER_TOKEN)


def _trim_history(history: list[dict], budget: int = MAX_HISTORY_TOKENS) -> list[dict]:
    history = [
        m for m in history
        if m.get("role") in ("user", "assistant")
        and m.get("content")
    ]
    if not history:
        return history

    # Separate system prompt from the rest
    sys_msgs  = [m for m in history if m["role"] == "system"]
    conv_msgs = [m for m in history if m["role"] != "system"]

    sys_tokens  = sum(_estimate_tokens(m.get("content") or "") for m in sys_msgs)
    remaining   = budget - sys_tokens

    # Walk backwards, keeping messages that fit
    kept = []
    used = 0
    for msg in reversed(conv_msgs):
        content = msg.get("content") or ""
        if isinstance(content, list):               # multi-part content
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        tokens = _estimate_tokens(content)
        if used + tokens > remaining and len(kept) >= 4:
            break
        kept.append(msg)
        used += tokens

    kept.reverse()

    trimmed = sys_msgs + kept
    if len(trimmed) < len(history):
        logger.info("History trimmed: %d → %d messages", len(history), len(trimmed))
    return trimmed


# ──────────────────────────────────────────────
# Tool-calling loop
# ──────────────────────────────────────────────

MAX_TOOL_ITERATIONS = 3    # prevent infinite loops


def run_agent(
    user_message: str,
    history: list[dict],
    language: str = "en",
    streaming: bool = False,
) -> dict[str, Any]:
    import time
    t_start = time.time()
    logger.warning("=== AGENT START ===")
    print(f"=== AGENT START ===")
    
    lang = language if language in SYSTEM_PROMPTS else "en"
    system_prompt = SYSTEM_PROMPTS[lang]

    # Build message list: system + (trimmed) history + new user message
    new_user_msg = {"role": "user", "content": user_message}
    messages = (
        [{"role": "system", "content": system_prompt}]
        + _trim_history(history)
        + [new_user_msg]
    )

    executed_tools: list[dict] = []

    if streaming:
        # Return generator immediately; tool loop happens inside _stream_with_tools
        gen = _stream_with_tools(messages, executed_tools)
        return {
            "reply":            gen,
            "tool_calls":       executed_tools,
            "updated_history":  history + [new_user_msg],
            "error":            None,
        }

    # Memory: track the last valid player_id found by player_search
    last_known_player_id = None

    # ── Non-streaming: full tool-calling loop ──────────────────
    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            import time
            t_llm_start = time.time()
            print(f"=== LLM CALL START (elapsed: {time.time()-t_start:.2f}s) ===")
            response = chat_completion(
                messages=messages,
                tools=TOOL_SCHEMAS,
                temperature=0.25,
                max_tokens=MAX_RESPONSE_TOKENS,
            )
            print(f"=== LLM CALL END (elapsed: {time.time()-t_start:.2f}s, LLM took: {time.time()-t_llm_start:.2f}s) ===")
        except LLMError as exc:
            return _error_result(str(exc), history + [new_user_msg])

        choice  = response["choices"][0]
        message = choice["message"]
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            # Final text answer
            reply = message.get("content") or ""
            updated_history = history + [
                new_user_msg,
                {"role": "assistant", "content": reply},
            ]
            return {
                "reply":           reply,
                "tool_calls":      executed_tools,
                "updated_history": updated_history,
                "error":           None,
            }

        # Execute each tool call and inject results back
        messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args_raw = tc["function"]["arguments"]

            try:
                fn_args = json.loads(fn_args_raw) if fn_args_raw else {}
            except (json.JSONDecodeError, TypeError):
                fn_args = {}

            # Safety guard — LLM sometimes sends null for no-arg tools
            if fn_args is None:
                fn_args = {}

            # ── PLAYER ID MEMORY ──────────────────────────────────
            if fn_name == "player_search":
                search_result, _ = _safe_execute_tool("player_search", fn_args)
                players_found = search_result.get("players", [])
                if players_found:
                    last_known_player_id = players_found[0]["player_id"]
                    logger.warning(
                        "=== PLAYER ID MEMORY: stored player_id=%s for '%s' ===",
                        last_known_player_id, fn_args.get("name", "?")
                    )
                    print(f"=== PLAYER ID MEMORY: stored {last_known_player_id} ===")
                result, success = search_result, bool(players_found)

            # ── PLAYER ID GUARD ───────────────────────────────────
            elif fn_name in ("physio_risk", "physio_timeseries", "nutri_generate_plan"):
                requested_id = fn_args.get("player_id")
                if (
                    last_known_player_id is not None
                    and requested_id != last_known_player_id
                    and (requested_id is None or requested_id > 100)
                ):
                    logger.warning(
                        "=== PLAYER ID CORRECTED: %s → %s ===",
                        requested_id, last_known_player_id
                    )
                    print(
                        f"=== PLAYER ID CORRECTED: LLM sent {requested_id}, "
                        f"using {last_known_player_id} from memory ==="
                    )
                    fn_args["player_id"] = last_known_player_id

                result, success = _safe_execute_tool(fn_name, fn_args)

            else:
                result, success = _safe_execute_tool(fn_name, fn_args)
            # ── END GUARD ─────────────────────────────────────────

            executed_tools.append({"tool": fn_name, "args": fn_args, "success": success})

            messages.append({
                "role":        "tool",
                "tool_call_id": tc["id"],
                "content":     json.dumps(result),
            })

    # If we hit MAX_TOOL_ITERATIONS without a text reply, force a summary
    logger.warning("Max tool iterations reached, forcing final answer.")
    try:
        messages.append({
            "role": "user",
            "content": "Summarize what you have found so far in a clear answer.",
        })
        import time
        t_synth = time.time()
        print(f"=== SYNTHESIS START (elapsed: {time.time()-t_start:.2f}s) ===")
        response = chat_completion(
            messages=messages,
            tools=None,     # disable tools to force text output
            temperature=0.3,
            max_tokens=MAX_RESPONSE_TOKENS,
        )
        print(f"=== SYNTHESIS END (elapsed: {time.time()-t_start:.2f}s, took: {time.time()-t_synth:.2f}s) ===")
        reply = response["choices"][0]["message"].get("content") or \
                "I gathered data but couldn't format the response. Please try again."
    except LLMError:
        reply = "I encountered an issue processing your request. Please try again."

    return {
        "reply":           reply,
        "tool_calls":      executed_tools,
        "updated_history": history + [new_user_msg, {"role": "assistant", "content": reply}],
        "error":           None,
    }


def _stream_with_tools(messages: list[dict], executed_tools: list):
    from .llm_client import chat_completion_stream

    last_known_player_id = None

    for iteration in range(MAX_TOOL_ITERATIONS):
        pending_tool_calls: list[dict] = []
        has_text = False

        for raw_chunk in chat_completion_stream(
            messages=messages,
            tools=TOOL_SCHEMAS,
            temperature=0.25,
            max_tokens=MAX_RESPONSE_TOKENS,
        ):
            if raw_chunk.startswith("data: __TOOL_CALL__:"):
                payload = raw_chunk[len("data: __TOOL_CALL__:"):]
                try:
                    pending_tool_calls.append(json.loads(payload.strip()))
                except json.JSONDecodeError:
                    pass

            elif raw_chunk.startswith("data: __ERROR__:"):
                err = raw_chunk[len("data: __ERROR__:"):]
                yield json.dumps({"type": "error", "data": err.strip()}) + "\n"
                return

            elif raw_chunk == "data: [DONE]\n\n":
                break

            elif raw_chunk.startswith("data: "):
                payload = raw_chunk[6:].strip()
                try:
                    chunk_data = json.loads(payload)
                    text = chunk_data.get("text", "")
                    if text:
                        has_text = True
                        yield json.dumps({"type": "text", "data": text}) + "\n"
                except json.JSONDecodeError:
                    pass

        # No tool calls → we're done streaming
        if not pending_tool_calls:
            yield json.dumps({"type": "done"}) + "\n"
            return

        # Execute tool calls, emit progress, inject results
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id":   tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in pending_tool_calls
            ],
        })

        for tc in pending_tool_calls:
            fn_name = tc["name"]
            try:
                fn_args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except (json.JSONDecodeError, TypeError):
                fn_args = {}

            # Safety guard — LLM sometimes sends null for no-arg tools
            if fn_args is None:
                fn_args = {}

            yield json.dumps({"type": "tool_start", "data": {"tool": fn_name, "args": fn_args}}) + "\n"

            if fn_name == "player_search":
                search_result, _ = _safe_execute_tool("player_search", fn_args)
                players_found = search_result.get("players", [])
                if players_found:
                    last_known_player_id = players_found[0]["player_id"]
                    print(f"=== STREAM PLAYER ID MEMORY: stored {last_known_player_id} ===")
                result, success = search_result, bool(players_found)

            elif fn_name in ("physio_risk", "physio_timeseries", "nutri_generate_plan"):
                requested_id = fn_args.get("player_id")
                if (
                    last_known_player_id is not None
                    and requested_id != last_known_player_id
                    and (requested_id is None or requested_id > 100)
                ):
                    print(
                        f"=== STREAM PLAYER ID CORRECTED: "
                        f"{requested_id} → {last_known_player_id} ==="
                    )
                    fn_args["player_id"] = last_known_player_id
                result, success = _safe_execute_tool(fn_name, fn_args)

            else:
                result, success = _safe_execute_tool(fn_name, fn_args)

            executed_tools.append({"tool": fn_name, "args": fn_args, "success": success})

            yield json.dumps({"type": "tool_end", "data": {"tool": fn_name, "success": success}}) + "\n"

            messages.append({
                "role":        "tool",
                "tool_call_id": tc["id"],
                "content":     json.dumps(result),
            })

        # Bug 2 fix: force complete data in synthesis, prevent 'as shown above'.
        messages.append({
            "role": "user",
            "content": (
                "Based on the tool results above, provide the complete "
                "formatted response now. Include ALL the data in your reply. "
                "Do not say as shown above or reference previous output. "
                "Present everything in full."
            ),
        })

    yield json.dumps({"type": "done"}) + "\n"


# ──────────────────────────────────────────────
# Safe tool executor
# ──────────────────────────────────────────────

def _safe_execute_tool(fn_name: str, fn_args: dict) -> tuple[Any, bool]:
    logger.warning("=== TOOL CALLED: %s with args: %s ===", fn_name, fn_args)
    print(f"=== TOOL CALLED: {fn_name} with args: {fn_args} ===")
    try:
        result = execute_tool(fn_name, fn_args or {})
        logger.warning("=== TOOL RESULT success: %s ===", str(result)[:200])
        print(f"=== TOOL RESULT: {str(result)[:200]} ===")
        return result, True
    except Exception as exc:
        logger.exception("Tool '%s' failed: %s", fn_name, exc)
        return {
            "error":   True,
            "message": f"TOOL_FAILURE: The tool '{fn_name}' failed: {exc}. "
                       f"Tell the user the service is temporarily unavailable. "
                       f"Do NOT provide any alternative information.",
        }, False


# ──────────────────────────────────────────────
# Error result builder
# ──────────────────────────────────────────────

def _error_result(error_msg: str, history: list[dict]) -> dict:
    return {
        "reply":           None,
        "tool_calls":      [],
        "updated_history": history,
        "error":           error_msg,
    }
