from django.apps import AppConfig
from django.conf import settings
import openai
import logging

logger = logging.getLogger(__name__)

class ChatConfig(AppConfig):
    name = 'chat'

    def ready(self):
        if hasattr(settings, 'OPEN_AI_TOKEN') and settings.OPEN_AI_TOKEN:
            openai.api_key = settings.OPEN_AI_TOKEN
            logger.info("OPEN_AI_TOKEN set from Django settings in ChatConfig.ready().")
        else:
            logger.error("OPEN_AI_TOKEN is not set in Django settings after ready().")

