import logging
from ..utils import generate_persuasion_messages
from ..models import User, ChatLog # Import User and ChatLog models
from ..ai_integration import AIIntegration # Import AIIntegration directly

logger = logging.getLogger(__name__)

# Instantiate AIIntegration for use within this stage handler
ai_integration_service = AIIntegration()

def handle_general_bot_stage(user, messaging_event):
    """
    Handles the logic for the GENERAL_BOT stage.
    """
    logger.info(f"Handling GENERAL_BOT stage for user {user.user_id}")
    message_text = messaging_event.get('message', {}).get('text')
    response_messages = []

    # Initial message after completing the exam
    if user.exam_question_counter == 0:
        response_messages.append(f"Congratulations, {user.first_name}! You've completed the mock exam!")
        # Use persuasion messages for initial entry to general bot stage after exam
        persuasion_msgs = generate_persuasion_messages(user, 'exam_finished')
        response_messages.extend(persuasion_msgs)
        response_messages.append("I can now act as your General Legal Assistant or Mentor. How can I assist you further today?")
        user.exam_question_counter = -1 # Mark as having sent the initial message for this stage
        user.save()
    elif user.exam_question_counter == -1: # Already sent initial message
        # General query handling
        if message_text:
            # Retrieve the last few messages for context to send to AI
            last_messages = ChatLog.objects.filter(user=user).order_by('-timestamp')[:5]
            conversation_context = "\n".join([f"{log.sender_type}: {log.message_content}" for log in last_messages[::-1]])
            
            prompt_context = {
                'user_first_name': user.first_name,
                'user_summary': user.summary if user.summary else "The user has not provided any specific preferences or context yet.",
                'message_text': message_text,
                'conversation_history': conversation_context
            }
            ai_response = ai_integration_service.generate_chat_response(
                user_id=user.user_id,
                system_prompt_name='GENERAL_BOT_SYSTEM_PROMPT',
                user_prompt_name='GENERAL_BOT_USER_PROMPT_TEMPLATE',
                prompt_category='GENERAL_BOT',
                prompt_context=prompt_context
            )
            
            if ai_response:
                response_messages.append(ai_response)
            else:
                fallback_message = "I'm sorry, I couldn't process that query at the moment. Can you please rephrase or ask for help on a different topic?"
                response_messages.append(fallback_message)
        else:
            response_messages.append("I'm here to help! What's on your mind?")
    
    return response_messages
