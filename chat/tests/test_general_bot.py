from django.test import TestCase
from unittest.mock import patch
from chat.models import User, ChatLog
from chat.tasks import process_messenger_message
from django.conf import settings
from django.utils import timezone # Import timezone utilities


# Mock settings for testing
settings.MESSENGER_VERIFY_TOKEN = 'test_verify_token'
settings.OPEN_AI_TOKEN = 'test_openai_token'


class GeneralBotStageTest(TestCase):
    def setUp(self):
        self.user_id = 'general_bot_user_psid'
        self.user_unregistered = User.objects.create(
            user_id=self.user_id + '_unreg',
            first_name='GeneralBotUnregUser',
            current_stage='GENERAL_BOT',
            exam_question_counter=0,
            is_registered_website_user=False
        )
        self.user_registered = User.objects.create(
            user_id=self.user_id + '_reg',
            first_name='GeneralBotRegUser',
            current_stage='GENERAL_BOT',
            exam_question_counter=0,
            is_registered_website_user=True
        )


    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.general_bot.ai_integration_service.generate_chat_response') # Updated mock
    def test_ai_response_logged_as_system_ai(self, mock_generate_chat_response, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_unregistered.exam_question_counter = -1
        self.user_unregistered.save()

        mock_ai_response = 'This is a mocked AI chat response.' # Updated response
        mock_generate_chat_response.return_value = mock_ai_response

        user_message_event = {
            'sender': {'id': self.user_unregistered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_general_query', 'text': 'Tell me about contract law'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Assert that the AI response was sent
        mock_send_messenger_message.assert_called_once_with(self.user_unregistered.user_id, mock_ai_response)

        # Assert that the AI response was logged to ChatLog
        chat_log = ChatLog.objects.filter(
            user=self.user_unregistered,
            sender_type='SYSTEM_AI',
            message_content=mock_ai_response
        ).first()
        self.assertIsNotNone(chat_log, 'SYSTEM_AI message was not logged.')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.general_bot.ai_integration_service.generate_chat_response')
    def test_general_bot_initial_transition_unregistered_user(self, mock_generate_chat_response, mock_send_messenger_message):
        # Simulate an initial message from an unregistered user
        user_message_event = {
            'sender': {'id': self.user_unregistered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_initial_general_unreg', 'text': 'Hello'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect 4 messages: congratulatory, 2 persuasion, general assistance
        self.assertEqual(mock_send_messenger_message.call_count, 4)
        
        call_list = mock_send_messenger_message.call_args_list

        # Check congratulatory message
        self.assertIn(f"Congratulations, {self.user_unregistered.first_name}! You've completed the mock exam!", call_list[0].args[1])
        
        # Check persuasion messages
        self.assertIn("To unlock comprehensive study materials", call_list[1].args[1])
        self.assertIn("It's the best way to prepare for the bar exam!", call_list[2].args[1])

        # Check general assistance message
        self.assertIn("I can now act as your General Legal Assistant or Mentor. How can I assist you further today?", call_list[3].args[1])

        self.user_unregistered.refresh_from_db()
        self.assertEqual(self.user_unregistered.exam_question_counter, -1)
        self.assertEqual(self.user_unregistered.current_stage, 'GENERAL_BOT')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.general_bot.ai_integration_service.generate_chat_response')
    def test_general_bot_initial_transition_registered_user(self, mock_generate_chat_response, mock_send_messenger_message):
        # Simulate an initial message from a registered user
        user_message_event = {
            'sender': {'id': self.user_registered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_initial_general_reg', 'text': 'Hello'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect 3 messages: congratulatory, 1 persuasion, general assistance
        self.assertEqual(mock_send_messenger_message.call_count, 3)
        
        call_list = mock_send_messenger_message.call_args_list

        # Check congratulatory message
        self.assertIn(f"Congratulations, {self.user_registered.first_name}! You've completed the mock exam!", call_list[0].args[1])
        
        # Check persuasion message
        self.assertIn("Excellent work, GeneralBotRegUser! Since you're already a registered user", call_list[1].args[1])

        # Check general assistance message
        self.assertIn("I can now act as your General Legal Assistant or Mentor. How can I assist you further today?", call_list[2].args[1])

        self.user_registered.refresh_from_db()
        self.assertEqual(self.user_registered.exam_question_counter, -1)
        self.assertEqual(self.user_registered.current_stage, 'GENERAL_BOT')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.general_bot.ai_integration_service.generate_chat_response') # Updated mock
    @patch('chat.stages.general_bot.generate_persuasion_messages') # Patch the persuasion messages
    def test_general_bot_ai_fallback_unregistered_user(self, mock_generate_persuasion_messages, mock_generate_chat_response, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_unregistered.exam_question_counter = -1
        self.user_unregistered.save()

        mock_generate_chat_response.return_value = None # Simulate AI fallback

        user_message_event = {
            'sender': {'id': self.user_unregistered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_fallback_unreg', 'text': 'gibberish'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect 1 message: only fallback
        self.assertEqual(mock_send_messenger_message.call_count, 1)
        
        call_list = mock_send_messenger_message.call_args_list

        # Check fallback message
        self.assertIn("I'm sorry, I couldn't process that query at the moment. Can you please rephrase or ask for help on a different topic?", call_list[0].args[1])
        
        # Assert persuasion messages were NOT called
        mock_generate_persuasion_messages.assert_not_called()

        self.user_unregistered.refresh_from_db()
        self.assertEqual(self.user_unregistered.current_stage, 'GENERAL_BOT')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.general_bot.ai_integration_service.generate_chat_response') # Updated mock
    @patch('chat.stages.general_bot.generate_persuasion_messages') # Patch the persuasion messages
    def test_general_bot_ai_fallback_registered_user(self, mock_generate_persuasion_messages, mock_generate_chat_response, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_registered.exam_question_counter = -1
        self.user_registered.save()

        mock_generate_chat_response.return_value = None # Simulate AI fallback

        user_message_event = {
            'sender': {'id': self.user_registered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_fallback_reg', 'text': 'unknown query'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect 1 message: only fallback
        self.assertEqual(mock_send_messenger_message.call_count, 1)
        
        call_list = mock_send_messenger_message.call_args_list

        # Check fallback message
        self.assertIn("I'm sorry, I couldn't process that query at the moment. Can you please rephrase or ask for help on a different topic?", call_list[0].args[1])
        
        # Assert persuasion messages were NOT called
        mock_generate_persuasion_messages.assert_not_called()

        self.user_registered.refresh_from_db()
        self.assertEqual(self.user_registered.current_stage, 'GENERAL_BOT')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.general_bot.ai_integration_service.generate_chat_response') # Updated mock
    def test_general_bot_normal_ai_response_no_persuasion(self, mock_generate_chat_response, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_unregistered.exam_question_counter = -1
        self.user_unregistered.save()

        mock_ai_response = "Here is a helpful response to your query."
        mock_generate_chat_response.return_value = mock_ai_response

        user_message_event = {
            'sender': {'id': self.user_unregistered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_normal_query', 'text': 'Tell me about Torts'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect 1 message: only AI response
        self.assertEqual(mock_send_messenger_message.call_count, 1)
        
        call_list = mock_send_messenger_message.call_args_list

        # Check AI response
        self.assertEqual(mock_ai_response, call_list[0].args[1])
        
        self.user_unregistered.refresh_from_db()
        self.assertEqual(self.user_unregistered.current_stage, 'GENERAL_BOT')