import logging
from celery import shared_task
from .models import User, ChatLog, Question
from .messenger_api import send_messenger_message
from .utils import ai_integration_service, get_random_exam_question # Import from utils
import datetime
import random
from django.utils import timezone # Import timezone utilities

# Import stage handlers
from .stages.onboarding import handle_onboarding_stage
from .stages.marketing import handle_marketing_stage
from .stages.mock_exam import handle_mock_exam_stage
from .stages.general_bot import handle_general_bot_stage

logger = logging.getLogger(__name__)

@shared_task
def process_messenger_message(messaging_event):
    """
    Celery task to process incoming Facebook Messenger messaging events.
    This task encapsulates the detailed message processing flow.
    """
    try:
        sender_id = messaging_event['sender']['id']
        message = messaging_event.get('message')
        postback = messaging_event.get('postback')
        message_text = None
        is_echo = False

        if message:
            message_text = message.get('text')
            is_echo = message.get('is_echo', False) # Check for message echoes

        logger.info(f"Processing message event for sender_id: {sender_id}, is_echo: {is_echo}, message_text: {message_text}")

        # Step 3: Echo Check (Admin Manual Override)
        if is_echo:
            # This is an admin's reply, process it as ADMIN_MANUAL
            admin_message = message_text
            # Find the user by PSID
            try:
                user = User.objects.get(user_id=sender_id)
                ChatLog.objects.create(
                    user=user,
                    sender_type='ADMIN_MANUAL',
                    message_content=admin_message
                )
                user.last_admin_reply_timestamp = timezone.now() # Use timezone.now()
                user.save()
                logger.info(f"Admin echo received and logged for user {sender_id}. last_admin_reply_timestamp updated.")
                return # STOP Processing for this message
            except User.DoesNotExist:
                logger.warning(f"Admin echo received for unknown user {sender_id}. Ignoring.")
                return # User not in our system, nothing to do

        # Step 4: Get User Data & Step 5: Save User Message
        try:
            user, created = User.objects.get_or_create(user_id=sender_id)
            if created:
                # For a new user, we might want to fetch their first name from Facebook
                # For now, let's just log and assign a placeholder
                logger.info(f"New user created: {sender_id}")
                user.first_name = "New User" # Placeholder, will implement fetching actual name later
                user.save()

            if message_text:
                ChatLog.objects.create(
                    user=user,
                    sender_type='USER',
                    message_content=message_text
                )
                user.last_interaction_timestamp = timezone.now() # Use timezone.now()
                user.save()
                logger.info(f"User message logged for {sender_id}: {message_text}")
            # If message_text is None or empty, we still proceed to stage handlers for processing.

        except Exception as e:
            logger.error(f"Error getting/creating user or saving message for {sender_id}: {e}", exc_info=True)
            return

        # Step 6: Admin Active Check (10-minute pause logic)
        if user.last_admin_reply_timestamp:
            time_difference = timezone.now() - user.last_admin_reply_timestamp # Use timezone.now()
            if time_difference < datetime.timedelta(minutes=10):
                logger.info(f"Admin active for user {sender_id}. Pausing AI response.")
                return # STOP Processing for this message

        # Step 7: Determine User Stage and dispatch to appropriate handler
        logger.info(f"Proceeding with AI logic for user {sender_id} in stage {user.current_stage}")

        response_messages = None
        if user.current_stage == 'ONBOARDING':
            response_messages = handle_onboarding_stage(user, messaging_event)
        elif user.current_stage == 'MARKETING':
            response_messages = handle_marketing_stage(user, messaging_event)
        elif user.current_stage == 'MOCK_EXAM':
            response_messages = handle_mock_exam_stage(user, messaging_event)
        elif user.current_stage == 'GENERAL_BOT':
            response_messages = handle_general_bot_stage(user, messaging_event)
        else:
            logger.warning(f"Unknown stage for user {sender_id}: {user.current_stage}. Defaulting to General Bot.")
            response_messages = handle_general_bot_stage(user, messaging_event)

        if response_messages:
            if isinstance(response_messages, list):
                for msg in response_messages:
                    if msg: # Only send non-empty messages
                        send_messenger_message(sender_id, msg)
                        logger.info(f"Sent stage-specific response to {sender_id}: {msg}")
            elif isinstance(response_messages, str):
                send_messenger_message(sender_id, response_messages)
                logger.info(f"Sent stage-specific response to {sender_id}: {response_messages}")
            else:
                logger.warning(f"Stage handler returned unsupported type: {type(response_messages)} for user {sender_id}.")

        # Step 11: Context Summarization Check (Sliding Window Algorithm)
        # After all replies are generated and saved, check if the total number of
        # unsummarized chat messages for this user exceeds 20.
        user_chat_logs = ChatLog.objects.filter(user=user).order_by('timestamp')
        if user_chat_logs.count() > 20:
            messages_to_summarize = user_chat_logs[:14] # Get the oldest 14 messages
            conversation_chunk = "\n".join([f"{log.sender_type}: {log.message_content}" for log in messages_to_summarize])

            new_summary_text = ai_integration_service.summarize_conversation(
                user_id=user.user_id,
                conversation_chunk=conversation_chunk,
                existing_summary=user.summary
            )
            # Ensure summary is less than 1,000 characters
            user.summary = (new_summary_text[:999] + '…') if len(new_summary_text) > 1000 else new_summary_text
            user.save()
            logger.info(f"Context summarized for user {sender_id}. New summary: {user.summary[:100]}...")

            # Optionally, delete the summarized messages to keep the log lean,
            # or mark them as summarized. For now, we'll just summarize.

    except Exception as e:
        logger.error(f"Unhandled error in process_messenger_message task: {e}", exc_info=True)


@shared_task
def check_inactive_users():
    """
    Celery periodic task to identify inactive users and send re-engagement messages.
    """
    logger.info("Running check_inactive_users task...")
    
    INACTIVITY_THRESHOLD_HOURS = 24 # Example: users inactive for 24 hours
    
    # Calculate the timestamp before which users are considered inactive
    inactive_since = timezone.now() - datetime.timedelta(hours=INACTIVITY_THRESHOLD_HOURS)
    
    # Get users who have not interacted since the threshold and are not in a mock exam
    # (to avoid interrupting them during an exam)
    inactive_users = User.objects.filter(
        last_interaction_timestamp__lt=inactive_since,
        current_stage__in=['ONBOARDING', 'MARKETING', 'GENERAL_BOT'] # Exclude MOCK_EXAM
    )
    
    follow_up_messages = [
        "Did you know that legal trivia can be fun? Try this: 'What is the highest court in the Philippines?'",
        "We are giving away a free reviewer PDF for those who are active! Don't miss out!",
        "Legal Maxim of the Day: 'Ignorantia juris non excusat.' Do you know what it means?",
        "Law school can be tough. Remember to take breaks and recharge! How are you doing today?",
        "Want to test your knowledge again? Our mock exam is ready for you!",
    ]
    
    for user in inactive_users:
        message_to_send = random.choice(follow_up_messages)
        send_messenger_message(user.user_id, message_to_send)
        logger.info(f"Sent re-engagement message to inactive user {user.user_id}: {message_to_send}")
        
        # Update last_interaction_timestamp to prevent immediate re-sending
        user.last_interaction_timestamp = timezone.now()
        user.save()
        
    logger.info(f"Finished checking inactive users. {inactive_users.count()} re-engagement messages sent.")