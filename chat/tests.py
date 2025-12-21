from django.test import TestCase
from unittest.mock import patch, MagicMock
import unittest.mock as mock
from datetime import datetime, timedelta
from freezegun import freeze_time
from chat.models import User, ChatLog, Question, Prompt
from legal.models import Course # Import Course model for testing
from chat.tasks import process_messenger_message, check_inactive_users, RE_ENGAGEMENT_MESSAGE_TYPES # Import check_inactive_users
from chat.ai_integration import AIIntegration # Import AIIntegration directly
from django.conf import settings
from django.utils import timezone # Import timezone utilities
from chat.utils import get_prompt
from django.core.cache import cache
from django.db.utils import IntegrityError
from django.db import transaction # Import transaction

import chat.prompts # Global import for chat.prompts

import openai # Import openai to mock its errors


# Mock settings for testing
settings.MESSENGER_VERIFY_TOKEN = 'test_verify_token'
settings.OPEN_AI_TOKEN = 'test_openai_token'


# This file has been split into smaller, more focused test files within the 'chat/tests/' directory.
# Please refer to the files in 'chat/tests/' for individual test cases.
# E.g., chat/tests/test_ai_integration.py, chat/tests/test_re_engagement.py, etc.