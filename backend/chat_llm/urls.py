from django.urls import path
from .views import ChatLLMView, ChatLLMStreamView

urlpatterns = [
    path('', ChatLLMView.as_view(), name='chat-llm'),
    path('stream/', ChatLLMStreamView.as_view(), name='chat-llm-stream'),
]
