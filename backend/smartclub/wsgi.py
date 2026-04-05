"""
WSGI config for smartclub project.

This module exposes the WSGI callable as a module-level variable named ``application``.
It is used by Django's development server and can be used in production with a WSGI server.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclub.settings')

application = get_wsgi_application()