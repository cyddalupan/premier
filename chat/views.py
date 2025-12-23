from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from django.conf import settings
from chat.task_queue import enqueue_task # NEW: Import enqueue_task
from chat.tasks import process_messenger_message # NEW: Import process_messenger_message as a regular function
from chat.tasks import check_inactive_users # NOW: Import check_inactive_users as a regular function
from chat.messenger_api import send_sender_action, send_messenger_message # NEW: Import send_sender_action and send_messenger_message
from .models import ChatLog, User
from chat.utils import get_random_loading_message # NEW: Import get_random_loading_message

logger = logging.getLogger(__name__)

@csrf_exempt
def webhook_callback(request):
    if request.method == 'GET':
        # Webhook GET request received, no need to log query params in production
        # Facebook webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == settings.MESSENGER_VERIFY_TOKEN:
            logger.info("Webhook verification successful.")
            return HttpResponse(challenge)
        else:
            logger.warning(f"Webhook verification failed. Mode: {mode}, Token: {token}")
            return HttpResponse('Error, wrong validation token', status=403)
    elif request.method == 'POST':
        try:
            request_body = request.body.decode('utf-8')
            # Webhook POST request received, avoid logging entire body for verbosity and security
            data = json.loads(request_body)
            
            # Facebook Messenger payload contains an 'entry' array
            # Each entry has a 'messaging' array of events
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event['sender']['id']
                    
                    # Send a random loading message first
                    loading_message = get_random_loading_message()
                    send_messenger_message(sender_id, loading_message)

                    # Then send typing_on immediately for quick feedback
                    send_sender_action(sender_id, 'typing_on')
                    
                    # Offload the processing of each messaging event to a Celery task
                    enqueue_task(process_messenger_message, messaging_event)
            
            return JsonResponse({"status": "received"}, status=200)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in Webhook POST request. Body: {request.body.decode('utf-8')}")
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            logger.error(f"Error processing Webhook POST request: {e}", exc_info=True)
            return HttpResponse(f'Error: {e}', status=500)
    logger.warning(f"Webhook received unsupported method: {request.method}")
    return HttpResponse('Method Not Allowed', status=405)

@csrf_exempt
def cron_dispatch(request):
    if request.method == 'POST':
        # TODO: Implement cron job dispatch logic here
        # This view will receive requests from an hourly cron trigger
        # and will dispatch various tasks (e.g., re-engagement, data collection)
        # to Celery based on the internal logic.
        logger.info("Cron dispatch URL hit. Acknowledging request.")
        enqueue_task(check_inactive_users) # NOW: Enqueue check_inactive_users as a regular function
        return JsonResponse({"status": "cron_dispatch_received", "message": "Cron job request acknowledged and inactive user check initiated."}, status=200)
    logger.warning(f"Cron dispatch URL received unsupported method: {request.method}")
    return HttpResponse('Method Not Allowed', status=405)
