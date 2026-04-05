#!/usr/bin/env python
"""
This file serves as the entry point for the Django management utility.  
It exposes the ``execute_from_command_line`` function and passes through
the command line arguments to manage the Django project.
"""
import os
import sys

def main() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclub.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            'Unable to import Django. Make sure it is installed and '
            'available on your PYTHONPATH environment variable.'
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()