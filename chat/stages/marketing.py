import logging
from ..models import User # Import User model to interact with it

logger = logging.getLogger(__name__)

def handle_marketing_stage(user, messaging_event):
    """
    Handles the logic for the MARKETING stage.
    """
    logger.info(f"Handling MARKETING stage for user {user.user_id}")
    message_text = messaging_event.get('message', {}).get('text', '').lower()
    response_messages = []

    # Generic USP
    usp_message = f"Hello {user.first_name}! Did you know our Review Center offers personalized AI-driven feedback for your practice exams? It's like having a private tutor!"
    
    # Prompt for mock exam
    mock_exam_offer = "Would you like to test your legal skills with a quick Mock Bar Exam today?"

    # Check if the user is responding to the mock exam offer
    if "yes" in message_text or "sure" in message_text or "start" in message_text or "exam" in message_text:
        response_messages.append("Great! Let's get you started with the Mock Bar Exam.")
        user.current_stage = 'MOCK_EXAM'
        user.save()
        logger.info(f"User {user.user_id} transitioned to MOCK_EXAM stage.")
    else:
        # Initial entry or no clear affirmative, send both messages
        response_messages.append(usp_message)
        response_messages.append(mock_exam_offer)
        logger.info(f"User {user.user_id} received marketing message and mock exam offer.")
        # User stays in MARKETING stage until they agree to mock exam or explicit command to change stage
    
    return response_messages if response_messages else None
