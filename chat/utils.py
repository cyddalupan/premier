from .ai_integration import AIIntegration
from .models import Question
import random
import logging

logger = logging.getLogger(__name__)

# Initialize AIIntegration outside tasks to reuse the instance
ai_integration_service = AIIntegration()

def get_random_exam_question():
    """
    Retrieves a random question from the Question bank.
    """
    questions = Question.objects.all()
    if questions.exists():
        return random.choice(questions)
    return None
