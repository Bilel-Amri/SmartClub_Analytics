from django.urls import path
from . import views

urlpatterns = [
    path("",         views.chat,         name="chat"),
    path("stream/",  views.chat_stream,  name="chat_stream"),
    path("reset/",   views.reset_chat,   name="chat_reset"),
    path("history/", views.chat_history, name="chat_history"),
]