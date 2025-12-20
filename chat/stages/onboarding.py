import logging
from ..models import User, ChatLog # Import User model to interact with it
from ..ai_integration import AIIntegration # Import AIIntegration

logger = logging.getLogger(__name__)

def handle_onboarding_stage(user, messaging_event):
    """
    Handles the logic for the ONBOARDING stage.
    Implements a clear two-step process: first, capture the user's name,
    then capture their academic status. The stage transitions to MARKETING
    only after academic status is successfully provided.
    :param user: The User object.
    :param messaging_event: The raw messaging event from Facebook.
    """
    ai_integration = AIIntegration() # Instantiate AIIntegration
    logger.info(f"Handling ONBOARDING stage for user {user.user_id}, sub_stage: {user.onboarding_sub_stage}")
    message_text = messaging_event.get('message', {}).get('text')
    response_messages = []

    # If first_name is not set, we need to ask for it.
    if not user.first_name:
        if user.onboarding_sub_stage == 'ASK_NAME' and message_text is not None:
            extracted_name = ai_integration.extract_name_from_message(message_text)
            if extracted_name:
                user.first_name = extracted_name
                user.current_stage = 'MARKETING' # Transition directly to MARKETING stage
                user.onboarding_sub_stage = None # Reset sub-stage
                user.save()
                logger.info(f"User {user.user_id} name set to: {user.first_name}. Transitioning to MARKETING stage.")
                response_messages.append(f"Nice to meet you, {user.first_name}! Ready to test your legal skills with a free AI-powered assessment exam? Just type 'yes' or 'start' to begin!")
            else:
                # If AI couldn't extract a name, re-ask.
                user.onboarding_sub_stage = 'ASK_NAME' # Keep in the same sub-stage
                user.save()
                response_messages.append("I couldn't quite catch your name. Could you please tell me your first name?")
        else:
            # If sub_stage is not ASK_NAME, or message_text is empty, ask for the name
            user.onboarding_sub_stage = 'ASK_NAME'
            user.save()
            response_messages.append("Ready to test your legal skills—for FREE? ⚖️\nTry our AI-powered assessment exam and get real-time results in Legal Basis, Legal Writing, and Legal Reasoning.\n📊 Instant feedback\n🤖 Smart AI evaluation\n⏱️ Takes only a few minutes\n\nStart your free assessment now!\n\nFirst, what's your name?")

    # Onboarding is fully complete (name is set)
    else:
        user.current_stage = 'MARKETING' # Ensure main stage is MARKETING
        user.onboarding_sub_stage = None # Reset sub-stage
        user.save()
        logger.info(f"User {user.user_id} already has name. Transitioning to MARKETING stage.")
        response_messages.append(f"Welcome back, {user.first_name}! You're all set. How can I help you today?")
    
    for response in response_messages:
        if response:
            ChatLog.objects.create(
                user=user,
                sender_type='SYSTEM_AI',
                message_content=response
            )
    return response_messages
