"""
WSGI config for premier project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sys # Added this line
from dotenv import load_dotenv # Import load_dotenv
from pathlib import Path # Import Path for absolute path

from django.core.wsgi import get_wsgi_application

# Log the Python path to help debug environment issues. This will appear in the Apache error log.
print(f"DEBUG: WSGI Python path: {sys.path}")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables before Django settings are read
dotenv_path = BASE_DIR / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'premier.settings')

application = get_wsgi_application()
