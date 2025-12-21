from django.test import TestCase
from unittest.mock import patch
from chat.models import User, ChatLog
from chat.tasks import process_messenger_message
from django.conf import settings
from django.utils import timezone # Import timezone utilities


# Mock settings for testing
settings.MESSENGER_VERIFY_TOKEN = 'test_verify_token'
settings.OPEN_AI_TOKEN = 'test_openai_token'


class AdminInterruptionTest(TestCase):
    def setUp(self):
        # Create a test user
        self.user_id = 'test_user_psid'
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name='Test',
            current_stage='GENERAL_BOT',
            exam_question_counter=-1 # Set to -1 to bypass initial congratulatory message in GENERAL_BOT stage
        )

    @patch('chat.tasks.send_messenger_message') # Patch where it's used in tasks.py
    @patch('chat.stages.general_bot.ai_integration_service.get_quick_reply')
    def test_admin_interruption_ai_continues_response(self, mock_get_quick_reply, mock_send_messenger_message):
        mock_get_quick_reply.return_value = 'Mocked quick reply text.'

        # Simulate an admin echo (user is the recipient of the admin message)
        admin_message_event = {
            'sender': {'id': 'PAGE_ID'}, # For an echo, sender is the Page
            'recipient': {'id': self.user_id}, # and recipient is the User
            'message': {
                'mid': 'm_test_admin',
                'text': 'Admin reply',
                'is_echo': True,
                'app_id': 123, # A different app_id, simulating a human admin
                'metadata': 'some metadata'
            },
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        # Process the admin echo
        process_messenger_message(admin_message_event)

        # Assert that the admin message is logged as ADMIN_MANUAL
        chat_log = ChatLog.objects.filter(user=self.user, sender_type='ADMIN_MANUAL').first()
        self.assertIsNotNone(chat_log)
        self.assertEqual(chat_log.message_content, 'Admin reply')

        # Simulate a user message after the admin echo
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {
                'mid': 'm_test_user',
                'text': 'User message after admin reply',
                'seq': 1
            },
            'timestamp': int(timezone.now().timestamp() * 1000) # Right after admin reply
        }

        # Reset mock for new assertions, as processing admin_message_event itself might have called send_messenger_message
        mock_send_messenger_message.reset_mock()
        mock_get_quick_reply.reset_mock()

        process_messenger_message(user_message_event)

        # Assert that send_messenger_message WAS called (AI responded)
        mock_get_quick_reply.assert_called_once()
        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user.user_id)
        self.assertEqual('Mocked quick reply text.', args[1])
