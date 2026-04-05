"""
chat_llm models:
  ChatSession   — one per user conversation thread
  ChatMessage   — individual turns (user/assistant)
  ToolCallLog   — audit trail for every tool invocation
"""
import uuid
from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    LANG_CHOICES = [
        ('auto', 'Auto-detect'),
        ('en',   'English'),
        ('fr',   'French'),
        ('ar',   'Arabic (MSA)'),
        ('tn',   'Tunisian Arabic'),
    ]
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='llm_sessions'
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)
    language_pref  = models.CharField(max_length=5, choices=LANG_CHOICES, default='auto')
    # Remember the last player discussed in this session
    last_player_id = models.IntegerField(null=True, blank=True)
    # Squad-browsing conversation state machine
    # Values: '' | 'awaiting_position' | 'awaiting_player' | 'awaiting_analysis'
    conv_state = models.CharField(max_length=30, blank=True, default='')
    # Ephemeral data for the current browsing step (position, player list, selected player)
    conv_data  = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'Session({self.user}, {self.language_pref}, {self.updated_at:%Y-%m-%d})'


class ChatMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant'), ('system', 'System')]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session    = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content    = models.TextField()
    language   = models.CharField(max_length=5, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        return f'Msg({self.role}, {self.created_at:%H:%M}): {self.content[:60]}'


class ToolCallLog(models.Model):
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session       = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='tool_logs')
    message       = models.ForeignKey(ChatMessage, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='tool_logs')
    tool_name     = models.CharField(max_length=60)
    request_json  = models.JSONField(default=dict)
    response_json = models.JSONField(default=dict)
    ok            = models.BooleanField(default=True)
    latency_ms    = models.IntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        status = 'OK' if self.ok else 'ERR'
        return f'Tool({self.tool_name}, {status}, {self.latency_ms}ms)'
