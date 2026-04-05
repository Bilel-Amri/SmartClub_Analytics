"""
Django settings overrides for the test suite.
Uses SQLite in-memory so no Postgres needed locally.
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclub.settings')

# Patch settings before Django loads them
from django.conf import settings

if not settings.configured:
    settings.configure()
