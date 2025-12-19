import logging
from celery import shared_task
from django.conf import settings
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

RE_ENGAGEMENT_MESSAGE_TYPES = [
    "Trivia/Fun Fact",
    "Giveaway/Promo",
    "Legal Maxim of the Day",
    "Success Story",
    "Quick Case Digest",
    "Mental Health Check"
]

INACTIVITY_THRESHOLD_HOURS = 24 # Example: users inactive for 24 hours

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
            # An echo event means our Page sent a message.
            # `sender_id` will be the Page ID, `recipient_id` will be the user's PSID.
            # We need to distinguish between echoes of our own bot messages and echoes of actual admin messages.
            
            # If the app_id in the message matches our FACEBOOK_APP_ID, it's our own bot's message.
            # In this case, we simply ignore the echo and do not stop processing.
            if message.get('app_id') and str(message.get('app_id')) == settings.FACEBOOK_APP_ID:
                logger.info(f"Received echo of our own message to user {messaging_event['recipient']['id']}. Ignoring.")
                return # Ignore our own echoes, don't process further
            else:
                # This is an echo from a different app_id, potentially a human admin
                admin_message = message_text
                user_psid_for_echo = messaging_event['recipient']['id'] # This is the user the admin replied to

                try:
                    user = User.objects.get(user_id=user_psid_for_echo)
                    ChatLog.objects.create(
                        user=user,
                        sender_type='ADMIN_MANUAL',
                        message_content=admin_message
                    )
                    user.last_admin_reply_timestamp = timezone.now()
                    user.save()
                    logger.info(f"Admin echo received and logged for user {user_psid_for_echo}. last_admin_reply_timestamp updated. Stopping AI processing.")
                    return # STOP Processing for this message (admin override is active)
                except User.DoesNotExist:
                    logger.warning(f"Admin echo received for unknown user {user_psid_for_echo}. Ignoring.")
                    return # User not in our system, nothing to do


        # Step 4: Get User Data & Step 5: Save User Message
        try:
            user, created = User.objects.get_or_create(user_id=sender_id)
            
            # If user's first_name is empty, do not automatically set it here.
            # The onboarding stage will explicitly ask for and set the name.
            if user.first_name in ["New User", "Guest", None, ""]:
                # If a new user and no message_text is provided, ensure first_name is None for onboarding to prompt.
                if not message_text or not message_text.strip():
                    user.first_name = None # Ensure it's explicitly None for the onboarding stage to pick up
                    logger.info(f"User {sender_id} first_name set to None for onboarding prompt.")
            # message_consumed_for_name remains False at this point,
            # it will be handled by handle_onboarding_stage if appropriate.
            user.save() # Save potential changes (like setting first_name to None)
            
            if created:
                logger.info(f"New user created: {sender_id}")
            
            if message_text:
                ChatLog.objects.create(
                    user=user,
                    sender_type='USER',
                    message_content=message_text
                )
                user.last_interaction_timestamp = timezone.now() # Use timezone.now()
                user.re_engagement_stage_index = 0 # Reset re-engagement stage on user interaction
                user.last_re_engagement_message_sent_at = None # Reset re-engagement timestamp
                user.save() # Save last_interaction_timestamp changes
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

        if response_messages: # This will now be true if the list is not empty
            for msg in response_messages:
                if msg: # Only process and send non-empty messages
                    # Save SYSTEM_AI message to ChatLog
                    ChatLog.objects.create(
                        user=user,
                        sender_type='SYSTEM_AI',
                        message_content=msg
                    )
                    logger.info(f"Logged SYSTEM_AI message for {sender_id}: {msg}")
    
                    send_messenger_message(sender_id, msg)
                    logger.info(f"Sent stage-specific response to {sender_id}: {msg}")

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


RE_ENGAGEMENT_INTERVALS = [
    (1, 2),    # Stage 1: 1 to 2 hours
    (5, 6),    # Stage 2: 5 to 6 hours
    (11, 12),  # Stage 3: 11 to 12 hours
    (21, 22),  # Stage 4: 21 to 22 hours
]

@shared_task
def check_inactive_users():
    """
    Celery periodic task to identify inactive users and send re-engagement messages
    based on a multi-stage schedule.
    """
    logger.info("Running check_inactive_users task for multi-stage re-engagement...")
    
    now = timezone.now()
    
    # Get all users who are not in a mock exam and have interacted at least once
    # and whose re_engagement_stage_index indicates they still have stages left.
    eligible_users = User.objects.filter(
        current_stage__in=['ONBOARDING', 'MARKETING', 'GENERAL_BOT'],
        last_interaction_timestamp__isnull=False,
        re_engagement_stage_index__lt=len(RE_ENGAGEMENT_INTERVALS)
    )
    
    re_engagement_attempts = 0

    for user in eligible_users:
        hours_since_last_interaction = (now - user.last_interaction_timestamp).total_seconds() / 3600

        # Determine the current stage the user is eligible for based on inactivity
        # This is the stage they *should* be in, not necessarily the one they've received a message for.
        current_eligible_stage_index = -1
        for i, (min_h, max_h) in enumerate(RE_ENGAGEMENT_INTERVALS):
            if min_h <= hours_since_last_interaction < max_h:
                current_eligible_stage_index = i
                break
        
        # If the user is eligible for a stage (current_eligible_stage_index != -1)
        # AND they haven't received a message for this specific stage yet (user.re_engagement_stage_index <= current_eligible_stage_index)
        # AND it's been long enough since the last re-engagement message was sent (to avoid spamming within the same stage window)
        if current_eligible_stage_index != -1 and user.re_engagement_stage_index <= current_eligible_stage_index:
            
            # Prevent sending multiple messages if cron runs more frequently than window duration
            can_send_message = True
            if user.last_re_engagement_message_sent_at and user.re_engagement_stage_index == current_eligible_stage_index + 1:
                # If a message for this stage has already been sent (stage index incremented)
                # Check if enough time has passed since that message was sent.
                # This ensures we don't resend within the same stage if the cron runs multiple times
                # while the user is still in the same time window and hasn't moved to the next stage.
                # We consider "enough time" to be roughly half the smallest stage interval (e.g., 30 mins for 1-hour window)
                if (now - user.last_re_engagement_message_sent_at).total_seconds() / 3600 < 0.5: # 30 minutes
                    can_send_message = False

            if can_send_message:
                logger.info(f"User {user.user_id} eligible for re-engagement stage {current_eligible_stage_index + 1}. Sending message.")
                
                selected_message_type = random.choice(RE_ENGAGEMENT_MESSAGE_TYPES)
                message_to_send = ai_integration_service.generate_re_engagement_message(
                    user_id=user.user_id,
                    current_stage=user.current_stage,
                    user_summary=user.summary,
                    message_type=selected_message_type
                )
                
                send_messenger_message(user.user_id, message_to_send)
                ChatLog.objects.create(
                    user=user,
                    sender_type='SYSTEM_AI',
                    message_content=message_to_send
                )
                logger.info(f"Sent and logged AI-composed '{selected_message_type}' re-engagement message to inactive user {user.user_id}: {message_to_send}")
                
                # Update user's state
                user.re_engagement_stage_index = current_eligible_stage_index + 1 # Move to the next stage
                user.last_re_engagement_message_sent_at = now
                user.save()
                
                re_engagement_attempts += 1
            else:
                logger.info(f"User {user.user_id} is in re-engagement stage {current_eligible_stage_index + 1}, but message recently sent. Skipping.")
        elif current_eligible_stage_index == -1 and user.re_engagement_stage_index < len(RE_ENGAGEMENT_INTERVALS):
            # If the user's inactivity duration is outside of all defined stages
            # (e.g., less than 1 hour or more than 22 hours) AND they haven't completed all stages,
            # we consider them as having progressed past current re-engagement stages.
            # This handles cases where they pass a stage without a cron trigger or fall outside
            # the last stage.
            if hours_since_last_interaction >= RE_ENGAGEMENT_INTERVALS[-1][1]: # If past the max of the last stage
                logger.info(f"User {user.user_id} has been inactive beyond all re-engagement stages. Marking as completed.")
                user.re_engagement_stage_index = len(RE_ENGAGEMENT_INTERVALS)
                user.save()


    logger.info(f"Finished checking inactive users. {re_engagement_attempts} re-engagement attempts made.")
