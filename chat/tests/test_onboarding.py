from django.test import TestCase
from unittest.mock import patch
from chat.models import User
from chat.tasks import process_messenger_message
from django.conf import settings
from django.utils import timezone # Import timezone utilities

# Mock settings for testing
settings.MESSENGER_VERIFY_TOKEN = 'test_verify_token'
settings.OPEN_AI_TOKEN = 'test_openai_token'


class OnboardingStageTest(TestCase):
    def setUp(self):
        self.user_id = 'onboarding_user_psid'
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name=None,
            current_stage='ONBOARDING',
            onboarding_sub_stage=None # Initial state for a brand new user
        )

    @patch('chat.tasks.send_messenger_message')
    def test_onboarding_asks_name_initially(self, mock_send_messenger_message):
        # Simulate an initial message (could be empty or any text, but no name yet)
        user_message_event = {
            'sender': {'id': self.user.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_initial', 'text': 'Hi'}, # User says hi
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.first_name)
        self.assertEqual(self.user.current_stage, 'ONBOARDING')
        self.assertEqual(self.user.onboarding_sub_stage, 'ASK_NAME')

        expected_message_part = "Ready to test your legal skills—for FREE? ⚖️"
        mock_send_messenger_message.assert_called_once()
        self.assertIn(expected_message_part, mock_send_messenger_message.call_args[0][1])
        self.assertIn("First, what's your name?", mock_send_messenger_message.call_args[0][1])
    
    @patch('chat.stages.onboarding.AIIntegration.extract_name_from_message') # Corrected patch target
    @patch('chat.tasks.send_messenger_message')
    def test_onboarding_captures_name_and_transitions_to_marketing(self, mock_send_messenger_message, mock_extract_name):
        # First, simulate the bot asking for the name
        self.user.onboarding_sub_stage = 'ASK_NAME'
        self.user.save()

        mock_extract_name.return_value = 'John Doe' # AI successfully extracts name

        # Simulate user providing their name
        user_message_event = {
            'sender': {'id': self.user.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_name_provided', 'text': 'My name is John Doe, nice to meet you!'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John Doe')
        self.assertEqual(self.user.current_stage, 'MARKETING') # Should transition to MARKETING
        self.assertIsNone(self.user.onboarding_sub_stage) # Sub-stage should be reset
        self.assertIsNone(self.user.academic_status) # Academic status should remain None

        mock_extract_name.assert_called_once_with('My name is John Doe, nice to meet you!')
        mock_send_messenger_message.assert_called_once_with(
            self.user.user_id,
            'Nice to meet you, John Doe! Ready to test your legal skills with a free AI-powered assessment exam? Just type \'yes\' or \'start\' to begin!'
        )

    @patch('chat.stages.onboarding.AIIntegration.extract_name_from_message') # Corrected patch target
    @patch('chat.tasks.send_messenger_message')
    def test_onboarding_re_asks_name_if_ai_fails_extraction(self, mock_send_messenger_message, mock_extract_name):
        # First, simulate the bot asking for the name
        self.user.onboarding_sub_stage = 'ASK_NAME'
        self.user.save()

        mock_extract_name.return_value = None # AI fails to extract a name

        # Simulate user sending a message that AI cannot parse as a name
        user_message_event = {
            'sender': {'id': self.user.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_no_name_found', 'text': 'I just want to start the exam.'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.first_name)
        self.assertEqual(self.user.current_stage, 'ONBOARDING')
        self.assertEqual(self.user.onboarding_sub_stage, 'ASK_NAME') # Should remain ASK_NAME

        mock_extract_name.assert_called_once_with('I just want to start the exam.')
        mock_send_messenger_message.assert_called_once_with(
            self.user.user_id,
            "I couldn't quite catch your name. Could you please tell me your first name?"
        )

    @patch('chat.stages.onboarding.AIIntegration.extract_name_from_message') # Corrected patch target
    @patch('chat.tasks.send_messenger_message')
    def test_onboarding_re_asks_name_if_empty_message(self, mock_send_messenger_message, mock_extract_name):
        # Simulate the bot asking for the name
        self.user.onboarding_sub_stage = 'ASK_NAME'
        self.user.save()

        mock_extract_name.return_value = None # AI will return None for empty string

        # Simulate user sending an empty message
        user_message_event = {
            'sender': {'id': self.user.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_empty_name', 'text': ''},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.first_name)
        self.assertEqual(self.user.current_stage, 'ONBOARDING')
        self.assertEqual(self.user.onboarding_sub_stage, 'ASK_NAME') # Should remain ASK_NAME

        mock_extract_name.assert_called_once_with('')
        mock_send_messenger_message.assert_called_once_with(
            self.user.user_id,
            "I couldn't quite catch your name. Could you please tell me your first name?"
        )

    @patch('chat.tasks.send_messenger_message')
    def test_onboarding_already_complete_transitions_to_marketing(self, mock_send_messenger_message):
        # Simulate user with both name and academic status already set, but still in ONBOARDING stage
        self.user.first_name = 'CompleteUser'
        self.user.academic_status = 'Bar Examinee'
        self.user.onboarding_sub_stage = None # Should be None if completed
        self.user.save()

        user_message_event = {
            'sender': {'id': self.user.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_already_complete', 'text': 'Hello again'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'MARKETING') # Should transition to MARKETING
        self.assertIsNone(self.user.onboarding_sub_stage) # Should remain None

        mock_send_messenger_message.assert_called_once_with(
            self.user.user_id,
            'Welcome back, CompleteUser! You\'re all set. How can I help you today?'
        )
