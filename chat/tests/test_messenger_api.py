import requests # Import requests
import json
import unittest
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import TestCase # Import Django's TestCase
from chat.messenger_api import send_messenger_message, send_sender_action, GRAPH_API_URL
from chat.models import User # Import the User model

class MessengerApiTests(TestCase): # Inherit from django.test.TestCase

    def setUp(self):
        # Mock Django settings for tests
        self.original_facebook_page_access_token = getattr(settings, 'FACEBOOK_PAGE_ACCESS_TOKEN', None)
        self.original_facebook_app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
        settings.FACEBOOK_PAGE_ACCESS_TOKEN = 'test_access_token'
        settings.FACEBOOK_APP_ID = 'test_app_id'
        
        # Create a test user for database-related tests
        self.user_id = 'test_recipient_id'
        self.user = User.objects.create(user_id=self.user_id, first_name="Test", is_messenger_reachable=True)
        
    def tearDown(self):
        # Restore original settings
        if self.original_facebook_page_access_token is not None:
            settings.FACEBOOK_PAGE_ACCESS_TOKEN = self.original_facebook_page_access_token
        if self.original_facebook_app_id is not None:
            settings.FACEBOOK_APP_ID = self.original_facebook_app_id
        
        # Clean up the test user
        User.objects.filter(user_id=self.user_id).delete()

    @patch('requests.post')
    def test_send_sender_action_typing_on(self, mock_post):
        """
        Test that send_sender_action correctly sends 'typing_on' action.
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        recipient_id = self.user_id
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

        recipient_id = self.user_id
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

        recipient_id = self.user_id
        message_text = 'Hello, test message!'

        result = send_messenger_message(recipient_id, message_text)

        self.assertTrue(result)
        mock_post.assert_called_once() # Ensure message was attempted to be sent
        mock_send_sender_action.assert_called_once_with(recipient_id, 'typing_off')

    @patch('requests.post')
    def test_unreachable_user_gets_marked_false_on_message_error(self, mock_post):
        """
        Test that is_messenger_reachable is set to False when Facebook API returns 'No matching user found' error for message.
        """
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = json.dumps({
            "error": {
                "message": "(#100) No matching user found",
                "type": "OAuthException",
                "code": 100,
                "error_subcode": 2018001,
                "fbtrace_id": "test_fbtrace_id"
            }
        })
        mock_http_error = requests.exceptions.HTTPError("Bad Request", response=mock_response)
        mock_post.side_effect = mock_http_error

        recipient_id = self.user_id
        message_text = "Test message"

        # Expect an HTTPError to be raised for message sending
        with self.assertRaises(requests.exceptions.HTTPError):
            send_messenger_message(recipient_id, message_text)

        # Refresh user data from DB and assert is_messenger_reachable is False
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_messenger_reachable)
        mock_post.assert_called_once() # Ensure API call was attempted

    @patch('requests.post')
    def test_unreachable_user_gets_marked_false_on_sender_action_error(self, mock_post):
        """
        Test that is_messenger_reachable is set to False when Facebook API returns 'No matching user found' error for sender action.
        """
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = json.dumps({
            "error": {
                "message": "(#100) No matching user found",
                "type": "OAuthException",
                "code": 100,
                "error_subcode": 2018001,
                "fbtrace_id": "test_fbtrace_id"
            }
        })
        mock_http_error = requests.exceptions.HTTPError("Bad Request", response=mock_response)
        mock_post.side_effect = mock_http_error

        recipient_id = self.user_id
        action = 'typing_off'

        result = send_sender_action(recipient_id, action)
        self.assertFalse(result) # Should return False on error

        # Refresh user data from DB and assert is_messenger_reachable is False
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_messenger_reachable)
        mock_post.assert_called_once() # Ensure API call was attempted

    @patch('requests.post')
    def test_unreachable_user_skips_message_api_call(self, mock_post):
        """
        Test that send_messenger_message does not make an API call if user is already marked as unreachable.
        """
        self.user.is_messenger_reachable = False
        self.user.save()

        recipient_id = self.user_id
        message_text = "Should not be sent"

        result = send_messenger_message(recipient_id, message_text)
        self.assertFalse(result)
        mock_post.assert_not_called() # API call should be skipped

    @patch('requests.post')
    def test_unreachable_user_skips_sender_action_api_call(self, mock_post):
        """
        Test that send_sender_action does not make an API call if user is already marked as unreachable.
        """
        self.user.is_messenger_reachable = False
        self.user.save()

        recipient_id = self.user_id
        action = 'typing_on'

        result = send_sender_action(recipient_id, action)
        self.assertFalse(result)
        mock_post.assert_not_called() # API call should be skipped
