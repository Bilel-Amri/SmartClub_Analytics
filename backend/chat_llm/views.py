"""
chat_llm API views:
  POST /api/chat-llm/         → JSON response (non-streaming, kept for compat)
  POST /api/chat-llm/stream/  → text/event-stream SSE (streaming, default in UI)

Request body:
  { "message": "...", "session_id": "optional-uuid", "language": "auto|en|fr|ar|tn" }
"""
import re
import json
import uuid
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import ChatSession
from .agent import detect_language, run_agent, run_agent_stream

# Compiled once — English words that must never be overridden by session memory
_CLEAR_EN = re.compile(
    r'\b(hello|hi|hey|how are you|good morning|good evening|good night|'
    r'thanks|thank you|yes|no|okay|alright|fine|great|nice|cool|sure|'
    r'what|when|where|who|why|how|help|please|sorry|perfect|awesome|'
    r'got it|i see|understood|i want|i need|i have|can you|could you|'
    r'tell me|show me|what is|what are|do you)\b',
    re.IGNORECASE,
)


def _resolve_session(request):
    """
    Parse request, resolve user + session, detect language.
    Returns (session, message, effective_lang) on success,
    or (None, None, Response) on error.
    """
    message    = (request.data.get('message') or '').strip()
    if not message:
        return None, None, Response({'error': 'message is required'}, status=400)

    session_id = request.data.get('session_id')
    lang_pref  = request.data.get('language', 'auto') or 'auto'

    # Resolve user — anonymous fallback in DEBUG
    user = request.user if request.user.is_authenticated else None
    if user is None:
        from django.conf import settings
        if not settings.DEBUG:
            return None, None, Response({'error': 'Authentication required'}, status=401)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if user is None:
            return None, None, Response(
                {'error': 'No users in DB — run: python manage.py createsuperuser'},
                status=500,
            )

    # Get or create session
    session = None
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id, user=user)
            if lang_pref != 'auto' and session.language_pref != lang_pref:
                session.language_pref = lang_pref
                session.save(update_fields=['language_pref'])
        except (ChatSession.DoesNotExist, Exception):
            pass
    if session is None:
        session = ChatSession.objects.create(user=user, language_pref=lang_pref)

    # Language detection
    detected_lang = detect_language(message, forced=lang_pref)

    # Session memory: use stored language when the message has no clear English markers.
    # This handles Tunisian/French users who type in derja transliteration (no TN regex match)
    # but haven't switched to English. Only override when _CLEAR_EN does NOT match.
    if lang_pref == 'auto' and detected_lang == 'en':
        stored = session.language_pref
        if (stored not in ('auto', 'en', '', None)
                and not _CLEAR_EN.search(message)):
            detected_lang = stored

    effective_lang = detected_lang

    # Persist non-English detected language to session
    if lang_pref == 'auto' and effective_lang not in ('auto', 'en'):
        if session.language_pref != effective_lang:
            session.language_pref = effective_lang
            session.save(update_fields=['language_pref'])

    return session, message, effective_lang


# ── Non-streaming view (kept for compatibility) ────────────────────────────────

class ChatLLMView(APIView):
    def post(self, request):
        session, message, effective_lang = _resolve_session(request)
        if session is None:
            return message  # message is the error Response here

        result = run_agent(session, message, effective_lang)
        return Response({'session_id': str(session.id), **result})


# ── Streaming view (SSE) ───────────────────────────────────────────────────────

class ChatLLMStreamView(APIView):
    def post(self, request):
        session, message, effective_lang = _resolve_session(request)
        if session is None:
            # Return error as SSE so the client can handle it uniformly
            err_json = json.dumps({'error': message.data.get('error', 'Bad request')})
            def _err_gen():
                yield f'data: {err_json}\n\n'
            resp = StreamingHttpResponse(
                streaming_content=_err_gen(),
                content_type='text/event-stream',
            )
            resp['Cache-Control'] = 'no-cache'
            return resp

        def _stream():
            try:
                yield from run_agent_stream(session, message, effective_lang)
            except Exception as exc:
                import json as _j
                yield f'data: {_j.dumps({"error": str(exc)})}\n\n'

        response = StreamingHttpResponse(
            streaming_content=_stream(),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'   # disable nginx buffering
        response['Access-Control-Allow-Origin'] = '*'
        return response
