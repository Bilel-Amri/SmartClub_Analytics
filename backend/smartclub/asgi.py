"""
ASGI config for smartclub project.

This module exposes the ASGI callable as a module-level variable named ``application``.
It enables asynchronous web servers and websocket support.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclub.settings')

application = get_asgi_application()