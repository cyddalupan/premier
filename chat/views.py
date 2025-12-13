from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from chat.messenger_api import send_messenger_message # Import the new function

logger = logging.getLogger(__name__)

@csrf_exempt
def webhook_callback(request):
    if request.method == 'GET':
        logger.info(f"Webhook GET request received. Query params: {request.GET}")
        # Facebook webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == '5a8ca116c293ae140ba1ff31489a9499087c5ed6b52cfda3':
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
            
            # Extract message text from the Facebook Messenger payload
            messaging_events = data.get('entry', [])[0].get('messaging', [])
            for event in messaging_events:
                if event.get('message') and event['message'].get('text'):
                    received_message = event['message']['text']
                    sender_id = event['sender']['id']
                    logger.info(f"Received message from {sender_id}: {received_message}")
                    
                    # Send the message back to the user
                    send_messenger_message(sender_id, received_message)
                    
                    return JsonResponse({"status": "received", "message": received_message, "sender_id": sender_id}, status=200)
            
            logger.info("No text message found in POST payload.")
            return JsonResponse({"status": "received", "message": "No text message found in payload."}, status=200)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in Webhook POST request. Body: {request.body.decode('utf-8')}")
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            logger.error(f"Error processing Webhook POST request: {e}", exc_info=True)
            return HttpResponse(f'Error: {e}', status=500)
    logger.warning(f"Webhook received unsupported method: {request.method}")
    return HttpResponse('Method Not Allowed', status=405)