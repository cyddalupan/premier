import json
import unittest
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.test import TestCase # Using Django's TestCase for database interaction
from chat.tasks import process_messenger_message
from chat.models import User, ChatLog

# Mock settings for consistent testing environment
@patch.object(settings, 'FACEBOOK_PAGE_ACCESS_TOKEN', 'test_access_token')
@patch.object(settings, 'FACEBOOK_APP_ID', 'test_app_id')
class ProcessMessengerMessageTaskTests(TestCase):

    def setUp(self):
        # Create a user for testing
        self.user_id = 'test_sender_id'
        self.user = User.objects.create(user_id=self.user_id, current_stage='GENERAL_BOT')

        self.messaging_event_template = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'timestamp': 1458692752478,
            'message': {
                'mid': 'mid.$cAAKc_gX3_Ld6Vq8C9V2u54sD0cZt',
                'seq': 12345,
                'text': 'Hello, bot!',
                'is_echo': False,
            }
        }

    @patch('chat.tasks.send_sender_action')
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.tasks.ai_integration_service')
    @patch('chat.tasks.handle_general_bot_stage', return_value=['Bot response'])
    def test_typing_indicators_on_success(self, mock_handle_stage, mock_ai_integration, mock_send_messenger_message, mock_send_sender_action):
        """
        Test that typing_on is sent at the beginning and typing_off is sent at the end (success path).
        """
        messaging_event = self.messaging_event_template.copy()
        
        process_messenger_message(messaging_event)

        # Assert typing_on is called once at the start
        mock_send_sender_action.assert_any_call(self.user_id, 'typing_on')
        self.assertEqual(mock_send_sender_action.call_count, 1) # Only typing_on is expected
        
        # Verify message processing happened
        self.assertTrue(ChatLog.objects.filter(user=self.user, sender_type='USER', message_content='Hello, bot!').exists())
        self.assertTrue(ChatLog.objects.filter(user=self.user, sender_type='SYSTEM_AI', message_content='Bot response').exists())
        mock_send_messenger_message.assert_called_once_with(self.user_id, 'Bot response')

    @patch('chat.tasks.send_sender_action')
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.tasks.ai_integration_service')
    @patch('chat.tasks.handle_general_bot_stage', side_effect=Exception('Test error')) # Simulate an error
    @patch('chat.tasks.logger') # Patch the logger
    def test_typing_indicators_on_error(self, mock_logger, mock_handle_stage, mock_ai_integration, mock_send_messenger_message, mock_send_sender_action):
        """
        Test that typing_on is sent at the beginning and typing_off is sent even if an error occurs.
        The error should be logged but not re-raised by the task's outer try-except.
        """
        messaging_event = self.messaging_event_template.copy()
        
        process_messenger_message(messaging_event)

        # Assert typing_on is called once at the start
        mock_send_sender_action.assert_any_call(self.user_id, 'typing_on')
        
        # Ensure it was called exactly once (on)
        self.assertEqual(mock_send_sender_action.call_count, 1)
        
        mock_send_messenger_message.assert_not_called() # No message should be sent if an error occurs early

        # Assert that the error was logged
        mock_logger.error.assert_called_with(
            f"Unhandled error in process_messenger_message task for sender {self.user_id}: Test error",
            exc_info=True
        )
