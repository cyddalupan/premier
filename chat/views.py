from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from django.conf import settings
from chat.tasks import process_messenger_message, check_inactive_users # Import the Celery tasks
from chat.messenger_api import send_messenger_message # Keep this import for now, might be used in tasks

logger = logging.getLogger(__name__)

@csrf_exempt
def webhook_callback(request):
    if request.method == 'GET':
        logger.info(f"Webhook GET request received. Query params: {request.GET}")
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
            logger.info(f"Webhook POST request received. Body: {request_body}")
            data = json.loads(request_body)
            
            # Facebook Messenger payload contains an 'entry' array
            # Each entry has a 'messaging' array of events
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    # Offload the processing of each messaging event to a Celery task
                    process_messenger_message.delay(messaging_event)
            
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
        check_inactive_users.delay() # Trigger the Celery task for inactive users
        return JsonResponse({"status": "cron_dispatch_received", "message": "Cron job request acknowledged and inactive user check initiated."}, status=200)
    logger.warning(f"Cron dispatch URL received unsupported method: {request.method}")
    return HttpResponse('Method Not Allowed', status=405)
