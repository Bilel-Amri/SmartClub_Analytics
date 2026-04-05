from django.contrib import admin
from .models import ChatSession, ChatMessage, ToolCallLog


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'language_pref', 'last_player_id', 'updated_at']
    list_filter   = ['language_pref']
    search_fields = ['user__username']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display  = ['id', 'session', 'role', 'language', 'created_at']
    list_filter   = ['role', 'language']


@admin.register(ToolCallLog)
class ToolCallLogAdmin(admin.ModelAdmin):
    list_display  = ['id', 'tool_name', 'ok', 'latency_ms', 'session', 'created_at']
    list_filter   = ['tool_name', 'ok']
    readonly_fields = ['request_json', 'response_json']
