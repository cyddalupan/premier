import json
import unittest
from unittest.mock import patch, MagicMock
from django.conf import settings
from chat.messenger_api import send_messenger_message, send_sender_action, GRAPH_API_URL

class MessengerApiTests(unittest.TestCase):

    def setUp(self):
        # Mock Django settings for tests
        self.original_facebook_page_access_token = getattr(settings, 'FACEBOOK_PAGE_ACCESS_TOKEN', None)
        self.original_facebook_app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
        settings.FACEBOOK_PAGE_ACCESS_TOKEN = 'test_access_token'
        settings.FACEBOOK_APP_ID = 'test_app_id'
        
    def tearDown(self):
        # Restore original settings
        if self.original_facebook_page_access_token is not None:
            settings.FACEBOOK_PAGE_ACCESS_TOKEN = self.original_facebook_page_access_token
        if self.original_facebook_app_id is not None:
            settings.FACEBOOK_APP_ID = self.original_facebook_app_id

    @patch('requests.post')
    def test_send_sender_action_typing_on(self, mock_post):
        """
        Test that send_sender_action correctly sends 'typing_on' action.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        recipient_id = 'test_recipient_id'
        action = 'typing_on'

        result = send_sender_action(recipient_id, action)

        self.assertTrue(result)
        mock_post.assert_called_once_with(
            GRAPH_API_URL,
            params={"access_token": settings.FACEBOOK_PAGE_ACCESS_TOKEN},
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "recipient": {"id": recipient_id},
                "sender_action": action
            })
        )

    @patch('requests.post')
    def test_send_sender_action_typing_off(self, mock_post):
        """
        Test that send_sender_action correctly sends 'typing_off' action.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        recipient_id = 'test_recipient_id'
        action = 'typing_off'

        result = send_sender_action(recipient_id, action)

        self.assertTrue(result)
        mock_post.assert_called_once_with(
            GRAPH_API_URL,
            params={"access_token": settings.FACEBOOK_PAGE_ACCESS_TOKEN},
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "recipient": {"id": recipient_id},
                "sender_action": action
            })
        )
    
    @patch('requests.post')
    @patch('chat.messenger_api.send_sender_action') # Patch send_sender_action within the module
    def test_send_messenger_message_calls_typing_off(self, mock_send_sender_action, mock_post):
        """
        Test that send_messenger_message calls send_sender_action with 'typing_off' after success.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'message_id': '123'} # Mock a successful response
        mock_post.return_value = mock_response

        recipient_id = 'test_recipient_id'
        message_text = 'Hello, test message!'

        result = send_messenger_message(recipient_id, message_text)

        self.assertTrue(result)
        mock_post.assert_called_once() # Ensure message was attempted to be sent
        mock_send_sender_action.assert_called_once_with(recipient_id, 'typing_off')
