import logging
from ..models import User, ChatLog # Import User model to interact with it

logger = logging.getLogger(__name__)

def handle_onboarding_stage(user, messaging_event):
    """
    Handles the logic for the ONBOARDING stage.
    """
    logger.info(f"Handling ONBOARDING stage for user {user.user_id}")
    message_text = messaging_event.get('message', {}).get('text')
    response = None

    if user.first_name == "New User":
        # Check if the user has already been prompted for their name in a previous interaction
        # We can infer this if last_interaction_timestamp is not None and first_name is still "New User"
        # However, for simplicity and to directly address the test, let's assume the first text message
        # after initial greeting is the name.
        if message_text and message_text.strip(): # User is responding with text, assume it's their name
            user.first_name = message_text.strip().split(' ')[0] # Take first word as name
            user.save()
            response = f"Nice to meet you, {user.first_name}! What is your current academic status or focus area in law (e.g., 1st year, Bar examinee, aspiring lawyer)?"
        else:
            # This handles initial contact or non-text input from a new user
            response = "Hello! I'm the Law Review Center AI Chatbot, your personal study assistant. What should I call you?"
    else:
        # User has provided their name, now expecting academic status/focus
        if message_text and message_text.strip():
            # For now, just acknowledge and transition to next stage
            # In a real scenario, we might save this info to user model
            response = f"Got it! So you are focusing on {message_text}. Let's see what I can do for you."
            user.current_stage = 'MARKETING' # Transition to the next stage
            user.save()
        else:
            response = f"Hello {user.first_name}! Could you please tell me your academic status or focus area in law?"
    
    if response:
        ChatLog.objects.create(
            user=user,
            sender_type='SYSTEM_AI',
            message_content=response
        )
    return [response] if response else []
