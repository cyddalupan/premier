import json
import logging
import requests
from django.conf import settings
from chat.models import User # Import the User model
import os 

logger = logging.getLogger(__name__)

# Facebook Graph API base URL
GRAPH_API_URL = "https://graph.facebook.com/v24.0/me/messages"

def _get_user_by_fb_id(fb_id: str):
    """Helper function to safely retrieve a User object by fb_id."""
    try:
        return User.objects.get(user_id=fb_id)
    except User.DoesNotExist:
        logger.warning(f"User with fb_id {fb_id} not found in the database.")
        return None

def send_messenger_message(recipient_id, message_text):
    """
    Sends a text message to a Facebook Messenger user.
    """
    user = _get_user_by_fb_id(recipient_id)
    if user and not user.is_messenger_reachable:
        logger.warning(f"Skipping message to unreachable user {recipient_id}.")
        return False

    raw_token_from_env = os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN')
    logger.info(f"Raw token from os.getenv (first 10 chars): {raw_token_from_env[:10] if raw_token_from_env else 'None'}...")

    params = {
        "access_token": settings.FACEBOOK_PAGE_ACCESS_TOKEN
    }
    logger.info(f"Using FACEBOOK_PAGE_ACCESS_TOKEN (first 10 chars): {settings.FACEBOOK_PAGE_ACCESS_TOKEN[:10] if settings.FACEBOOK_PAGE_ACCESS_TOKEN else 'None'}...")
    logger.info(f"Full params for API call: {params}")
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    
    try:
        response = requests.post(GRAPH_API_URL, params=params, headers=headers, data=data)
        response.raise_for_status() # Raise an exception for HTTP errors
        logger.info(f"Message sent to {recipient_id}: {message_text}")
        logger.info(f"Facebook API response: {response.json()}")
        send_sender_action(recipient_id, 'typing_off') # Turn off typing indicator after sending message
        return True
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error sending message to {recipient_id}: {e}")
        error_response = e.response.text
        logger.error(f"Facebook API Error Response: {error_response}") # Log the full error response
        
        # Check for specific unreachability error
        try:
            error_data = json.loads(error_response)
            if error_data.get("error", {}).get("code") == 100 and \
               error_data.get("error", {}).get("error_subcode") == 2018001:
                if user:
                    user.is_messenger_reachable = False
                    user.save()
                    logger.warning(f"User {recipient_id} marked as unreachable due to Facebook API error.")
        except json.JSONDecodeError:
            logger.error(f"Could not decode JSON from error response: {error_response}")
        
        raise # Re-raise the exception for critical message sending failures
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error sending message to {recipient_id}: {e}", exc_info=True)
        return False

def send_sender_action(recipient_id, action):
    """
    Sends a sender action (e.g., 'typing_on', 'typing_off', 'mark_seen') to a Facebook Messenger user.
    """
    user = _get_user_by_fb_id(recipient_id)
    if user and not user.is_messenger_reachable:
        logger.debug(f"Skipping sender action '{action}' to unreachable user {recipient_id}.")
        return False

    params = {
        "access_token": settings.FACEBOOK_PAGE_ACCESS_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "sender_action": action
    })

    try:
        response = requests.post(GRAPH_API_URL, params=params, headers=headers, data=data)
        response.raise_for_status()
        logger.info(f"Sender action '{action}' sent to {recipient_id}")
        return True
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error sending sender action '{action}' to {recipient_id}: {e}")
        error_response = e.response.text
        logger.error(f"Facebook API Error Response for sender action: {error_response}")

        # Check for specific unreachability error
        try:
            error_data = json.loads(error_response)
            if error_data.get("error", {}).get("code") == 100 and \
               error_data.get("error", {}).get("error_subcode") == 2018001:
                if user:
                    user.is_messenger_reachable = False
                    user.save()
                    logger.warning(f"User {recipient_id} marked as unreachable due to Facebook API error.")
        except json.JSONDecodeError:
            logger.error(f"Could not decode JSON from error response: {error_response}")
        
        return False # Do not re-raise for sender actions
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error sending sender action '{action}' to {recipient_id}: {e}", exc_info=True)
        return False