import logging
from ..utils import ai_integration_service, generate_persuasion_messages
from ..models import User, ChatLog # Import User and ChatLog models

logger = logging.getLogger(__name__)

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
            
            ai_response = ai_integration_service.get_quick_reply(
                user_id=user.user_id,
                conversation_history=conversation_context + f"\nUser: {message_text}"
            )
            
            if ai_response:
                response_messages.append(ai_response)
            else:
                fallback_message = "I'm sorry, I couldn't process that query at the moment. Can you please rephrase?"
                response_messages.append(fallback_message)
                # If AI response is a fallback and user is not registered, inject general chat persuasion
                if not user.is_registered_website_user:
                    persuasion_msgs = generate_persuasion_messages(user, 'general_chat')
                    response_messages.extend(persuasion_msgs)
        else:
            response_messages.append("I'm here to help! What's on your mind?")
    
    return response_messages
