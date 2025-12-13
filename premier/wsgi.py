"""
WSGI config for premier project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from dotenv import load_dotenv # Import load_dotenv
from pathlib import Path # Import Path for absolute path

from django.core.wsgi import get_wsgi_application

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables before Django settings are read
dotenv_path = BASE_DIR / '.env'
if dotenv_path.exists():
    load_success = load_dotenv(dotenv_path=dotenv_path)
    print(f"DEBUG: .env loaded: {load_success} from {dotenv_path}") # This will go to Apache error log
else:
    print(f"DEBUG: .env file not found at {dotenv_path}") # This will go to Apache error log

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'premier.settings')

application = get_wsgi_application()
