"""
URL configuration for the smartclub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/stable/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('scout/', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('physio/', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('nutri/', include('nutri.urls'))
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    # Legacy JWT endpoints kept for backwards compat
    path('api/token/', include('users.urls')),
    path('api/scout/', include('scout.urls')),
    # Legacy Physio API retained for compatibility with existing tests/tools.
    path('api/physio/', include('physio.urls')),
    path('api/v2/physio/', include('physio.urls_v2')),
    path('api/nutri/', include('nutri.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/chat-llm/', include('chat_llm.urls')),
    path('api/dashboard/', include('dashboard.urls')),
    path('api/monitoring/', include('monitoring.urls')),
]
