from django.test import TestCase, TransactionTestCase
from unittest.mock import patch, MagicMock
from chat.models import User, Question, ExamResult, ChatLog
from chat.ai_integration import AIIntegration
from django.conf import settings
from chat.utils import get_prompt
import openai
from django.utils import timezone
import datetime

# Mock settings for testing
settings.OPEN_AI_TOKEN = 'test_openai_token'


class TestAIIntegration(TestCase):
    def setUp(self):
        self.ai_integration_service = AIIntegration()
        self.user = User.objects.create(
            user_id='test_user_ai',
            first_name='TestUser',
            current_stage='MARKETING',
            summary='User is interested in mock exams and needs motivation.',
            last_interaction_timestamp=timezone.now()
        )
        User.objects.create(user_id='test_user', first_name='TestErrorUser', current_stage='GENERAL_BOT')
        self.conversation_history = "USER: Hello bot\nSYSTEM_AI: Hi TestUser, how can I help you?"
        ChatLog.objects.create(user=self.user, sender_type='USER', message_content='Hello bot')
        ChatLog.objects.create(user=self.user, sender_type='SYSTEM_AI', message_content='Hi TestUser, how can I help you?')

    @patch('openai.chat.completions.create')
    def test_generate_re_engagement_message_success(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(strip=MagicMock(return_value='AI-composed re-engagement message!'))
                )
            )]
        )

        message = self.ai_integration_service.generate_re_engagement_message(
            user_id=self.user.user_id,
            first_name=self.user.first_name,
            current_stage=self.user.current_stage,
            user_summary=self.user.summary,
            conversation_history=self.conversation_history
        )

        self.assertEqual(message, 'AI-composed re-engagement message!')
        mock_create.assert_called_once()
        call_args, call_kwargs = mock_create.call_args
        self.assertEqual(call_kwargs['model'], 'gpt-5-mini')
        self.assertIn("friendly and highly creative AI assistant", call_kwargs['messages'][0]['content'])

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error'))
    def test_generate_re_engagement_message_openai_error_fallback(self, mock_create):
        message = self.ai_integration_service.generate_re_engagement_message(
            user_id=self.user.user_id,
            first_name=self.user.first_name,
            current_stage=self.user.current_stage,
            user_summary=self.user.summary,
            conversation_history=self.conversation_history
        )
        self.assertEqual(message, 'Hello! We missed you. How can I help you today?')
        mock_create.assert_called_once()

    @patch('openai.chat.completions.create', side_effect=Exception('Generic Error'))
    def test_generate_re_engagement_message_generic_error_fallback(self, mock_create):
        message = self.ai_integration_service.generate_re_engagement_message(
            user_id=self.user.user_id,
            first_name=self.user.first_name,
            current_stage=self.user.current_stage,
            user_summary=self.user.summary,
            conversation_history=self.conversation_history
        )
        self.assertEqual(message, 'Hi there! Just checking in. Let me know if you have any questions.')
        mock_create.assert_called_once()

    @patch('chat.ai_integration.openai.chat.completions.create', side_effect=openai.OpenAIError('API Error Test Message for Chat Response'))
    @patch('chat.ai_integration.get_prompt', side_effect=['System Prompt Content', 'Simple user prompt'])
    def test_generate_chat_response_openai_error_logs_and_returns_none(self, mock_get_prompt, mock_create):
        with self.assertLogs('chat', level='ERROR') as cm:
            result = self.ai_integration_service.generate_chat_response(
                user_id='test_user',
                system_prompt_name='GENERAL_BOT_SYSTEM_PROMPT',
                user_prompt_name='GENERAL_BOT_USER_PROMPT_TEMPLATE',
                prompt_category='GENERAL_BOT',
                prompt_context={'user_message': 'Hello'},
            )

            self.assertIsNone(result)
            mock_create.assert_called_once()
            self.assertEqual(mock_get_prompt.call_count, 2)
            self.assertTrue(any(
                "ERROR:chat.ai_integration:OpenAI API error during chat response generation: API Error Test Message for Chat Response" in log_entry
                for log_entry in cm.output
            ))


class TestUserStrengthAssessment(TestCase):
    def setUp(self):
        self.ai_integration_service = AIIntegration()
        self.user = User.objects.create(
            user_id='assessment_user_psid',
            first_name='AssessmentUser',
            current_stage='MOCK_EXAM',
            exam_question_counter=8
        )
        self.q_criminal1 = Question.objects.create(category='Criminal Law', question_text='Crim Q1', expected_answer='Crim A1')
        self.q_criminal2 = Question.objects.create(category='Criminal Law', question_text='Crim Q2', expected_answer='Crim A2')
        self.q_civil1 = Question.objects.create(category='Civil Law', question_text='Civil Q1', expected_answer='Civil A1')
        self.q_civil2 = Question.objects.create(category='Civil Law', question_text='Civil Q2', expected_answer='Civil A2')
        self.q_labor1 = Question.objects.create(category='Labor Law', question_text='Labor Q1', expected_answer='Labor A1')
        self.q_labor2 = Question.objects.create(category='Labor Law', question_text='Labor Q2', expected_answer='Labor A2')
        self.q_tax1 = Question.objects.create(category='Tax Law', question_text='Tax Q1', expected_answer='Tax A1')
        self.q_tax2 = Question.objects.create(category='Tax Law', question_text='Tax Q2', expected_answer='Tax A2')

        ExamResult.objects.create(user=self.user, question=self.q_criminal1, score=90)
        ExamResult.objects.create(user=self.user, question=self.q_criminal2, score=95)
        ExamResult.objects.create(user=self.user, question=self.q_civil1, score=88)
        ExamResult.objects.create(user=self.user, question=self.q_civil2, score=85)
        ExamResult.objects.create(user=self.user, question=self.q_labor1, score=60)
        ExamResult.objects.create(user=self.user, question=self.q_labor2, score=65)
        ExamResult.objects.create(user=self.user, question=self.q_tax1, score=50)
        ExamResult.objects.create(user=self.user, question=self.q_tax2, score=55)

    @patch('openai.chat.completions.create')
    @patch('chat.tasks.send_messenger_message')
    def test_assessment_generation_with_strengths(self, mock_send_messenger_message, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Based on your performance, you show strong aptitude in Criminal Law and Civil Law.')
                    )
                )
            )]
        )

        assessment_message = self.ai_integration_service.generate_strength_assessment(self.user)

        self.assertIn('strong aptitude in Criminal Law and Civil Law', assessment_message)
        mock_create.assert_called_once()
        
        call_args, call_kwargs = mock_create.call_args
        self.assertIn('Criminal Law (Avg Score: 92.5)', call_kwargs['messages'][1]['content'])
        self.assertEqual(call_kwargs['model'], 'gpt-5.2')

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error Test Message'))
    def test_assessment_generation_openai_error(self, mock_create):
        with self.assertLogs('chat', level='INFO') as cm:
            assessment_message = self.ai_integration_service.generate_strength_assessment(self.user)

            self.assertEqual(assessment_message, "I'm sorry, I couldn't generate your strength assessment at the moment. Please try again later.")
            mock_create.assert_called_once()
            
            error_log_found = False
            for log_entry in cm.output:
                if "ERROR:chat.ai_integration:OpenAI API error during strength assessment generation" in log_entry:
                    error_log_found = True
                    self.assertIn("OpenAI API error during strength assessment generation: API Error Test Message", log_entry)
            
            self.assertTrue(error_log_found, "Expected OpenAI error log not found.")


class AIIntegrationNameExtractionTest(TestCase):
    def setUp(self):
        self.ai_integration_service = AIIntegration()

    @patch('openai.chat.completions.create')
    def test_extract_name_from_simple_message(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Kaido')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("Kaido")
        self.assertEqual(name, 'Kaido')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'Kaido'")

    @patch('openai.chat.completions.create')
    def test_extract_name_from_message_with_my_name_is_phrase(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Kaido')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("My name is Kaido.")
        self.assertEqual(name, 'Kaido')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'My name is Kaido.'")

    @patch('openai.chat.completions.create')
    def test_extract_name_from_message_with_i_am_phrase(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Jane')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("Hello, I am Jane.")
        self.assertEqual(name, 'Jane')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'Hello, I am Jane.'")

    @patch('openai.chat.completions.create')
    def test_extract_name_from_message_with_its_phrase(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Bob')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("It's Bob, nice to meet you.")
        self.assertEqual(name, 'Bob')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'It's Bob, nice to meet you.'")

    @patch('openai.chat.completions.create')
    def test_extract_name_from_message_with_just_word(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Sarah')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("Just Sarah.")
        self.assertEqual(name, 'Sarah')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'Just Sarah.'")

    @patch('openai.chat.completions.create')
    def test_extract_name_with_punctuation(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Kaido')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("Kaido!")
        self.assertEqual(name, 'Kaido')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'Kaido!'")

    @patch('openai.chat.completions.create')
    def test_extract_name_no_name_found_returns_none(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='[NO_NAME]')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("Hello there, how are you?")
        self.assertEqual(name, 'User')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'Hello there, how are you?'")

    @patch('openai.chat.completions.create')
    def test_extract_name_what_is_your_name_query_returns_none(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='[NO_NAME]')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("What is your name?")
        self.assertEqual(name, 'User')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'What is your name?'")

    @patch('openai.chat.completions.create')
    def test_extract_name_empty_message_returns_none(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='[NO_NAME]')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("")
        self.assertEqual(name, 'User')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: ''")

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error'))
    def test_extract_name_openai_error_returns_none(self, mock_create):
        name = self.ai_integration_service.extract_name_from_message("My name is Test User.")
        self.assertEqual(name, 'User')
        mock_create.assert_called_once()


class AIIntegrationGPT52UsageTest(TransactionTestCase):
    def setUp(self):
        self.ai_integration_service = AIIntegration()
        self.user_general_bot = User.objects.create(user_id='general_user', current_stage='GENERAL_BOT', gpt_5_2_daily_count=0, gpt_5_2_last_reset_date=timezone.now().date())
        self.user_onboarding = User.objects.create(user_id='onboarding_user', current_stage='ONBOARDING', gpt_5_2_daily_count=0, gpt_5_2_last_reset_date=timezone.now().date())
        
        self.patcher_get_prompt = patch('chat.ai_integration.get_prompt', side_effect=lambda name, category: f"{name} content")
        self.mock_get_prompt = self.patcher_get_prompt.start()

    def tearDown(self):
        self.patcher_get_prompt.stop()


    @patch('openai.chat.completions.create')
    @patch('chat.ai_integration.reset_gpt_5_2_usage_if_new_day')
    def test_general_bot_uses_gpt_5_2_under_limit(self, mock_reset, mock_create):
        # User is in GENERAL_BOT, count is 0
        self.user_general_bot.gpt_5_2_daily_count = 0
        self.user_general_bot.save()

        mock_create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="AI Response"))])

        response = self.ai_integration_service.generate_chat_response(
            user_id=self.user_general_bot.user_id,
            system_prompt_name='SYSTEM', user_prompt_name='USER', prompt_category='GENERAL_BOT', prompt_context={}
        )

        self.assertEqual(response, "AI Response")
        mock_reset.assert_called_once_with(self.user_general_bot)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['model'], 'gpt-5.2')
        
        # Refresh user to get updated count
        self.user_general_bot.refresh_from_db()
        self.assertEqual(self.user_general_bot.gpt_5_2_daily_count, 1)

    @patch('openai.chat.completions.create')
    @patch('chat.ai_integration.reset_gpt_5_2_usage_if_new_day')
    def test_general_bot_falls_back_to_gpt_5_mini_over_limit(self, mock_reset, mock_create):
        # User is in GENERAL_BOT, count is 10
        self.user_general_bot.gpt_5_2_daily_count = 10
        self.user_general_bot.save()

        mock_create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="AI Response"))])

        response = self.ai_integration_service.generate_chat_response(
            user_id=self.user_general_bot.user_id,
            system_prompt_name='SYSTEM', user_prompt_name='USER', prompt_category='GENERAL_BOT', prompt_context={}
        )

        self.assertEqual(response, "AI Response")
        mock_reset.assert_called_once_with(self.user_general_bot)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['model'], 'gpt-5-mini')
        
        # Count should not increment further
        self.user_general_bot.refresh_from_db()
        self.assertEqual(self.user_general_bot.gpt_5_2_daily_count, 10)

    @patch('openai.chat.completions.create')
    @patch('chat.ai_integration.reset_gpt_5_2_usage_if_new_day')
    def test_non_general_bot_stage_uses_gpt_5_mini_no_count_increment(self, mock_reset, mock_create):
        # User is in ONBOARDING, count is 0
        self.user_onboarding.gpt_5_2_daily_count = 0
        self.user_onboarding.save()

        mock_create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="AI Response"))])

        response = self.ai_integration_service.generate_chat_response(
            user_id=self.user_onboarding.user_id,
            system_prompt_name='SYSTEM', user_prompt_name='USER', prompt_category='ONBOARDING', prompt_context={}
        )

        self.assertEqual(response, "AI Response")
        mock_reset.assert_not_called() # Should not call reset for non-general-bot
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['model'], 'gpt-5-mini') # Default model for general chat
        
        # Count should not increment
        self.user_onboarding.refresh_from_db()
        self.assertEqual(self.user_onboarding.gpt_5_2_daily_count, 0)
    
    @patch('openai.chat.completions.create')
    @patch('chat.ai_integration.reset_gpt_5_2_usage_if_new_day')
    def test_general_bot_resets_count_on_new_day_then_uses_gpt_5_2(self, mock_reset, mock_create):
        # Set user's last reset date to a past date
        self.user_general_bot.gpt_5_2_last_reset_date = (timezone.now().date() - datetime.timedelta(days=1))
        self.user_general_bot.gpt_5_2_daily_count = 5 # Some count from yesterday
        self.user_general_bot.save()

        mock_create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="AI Response"))])
        mock_reset.side_effect = lambda user: setattr(user, 'gpt_5_2_daily_count', 0) or setattr(user, 'gpt_5_2_last_reset_date', timezone.now().date()) or user.save()

        response = self.ai_integration_service.generate_chat_response(
            user_id=self.user_general_bot.user_id,
            system_prompt_name='SYSTEM', user_prompt_name='USER', prompt_category='GENERAL_BOT', prompt_context={}
        )

        self.assertEqual(response, "AI Response")
        mock_reset.assert_called_once_with(self.user_general_bot)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['model'], 'gpt-5.2')
        
        self.user_general_bot.refresh_from_db()
        self.assertEqual(self.user_general_bot.gpt_5_2_daily_count, 1) # Should be 1 after reset and new use
        self.assertEqual(self.user_general_bot.gpt_5_2_last_reset_date, timezone.now().date())

    @patch('openai.chat.completions.create')
    @patch('chat.ai_integration.reset_gpt_5_2_usage_if_new_day')
    def test_general_bot_fallback_after_limit_in_sequence(self, mock_reset, mock_create):
        # Set user's gpt_5_2_daily_count to 9 initially
        self.user_general_bot.gpt_5_2_daily_count = 9
        self.user_general_bot.save()
        
        mock_create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="AI Response"))])

        # --- 10th call ---
        self.ai_integration_service.generate_chat_response(
            user_id=self.user_general_bot.user_id,
            system_prompt_name='SYSTEM', user_prompt_name='USER', prompt_category='GENERAL_BOT', prompt_context={}
        )

        user_after_10th = User.objects.get(user_id=self.user_general_bot.user_id)
        self.assertEqual(user_after_10th.gpt_5_2_daily_count, 10)
        self.assertEqual(mock_create.call_args.kwargs['model'], 'gpt-5.2')

        # --- 11th call ---
        self.ai_integration_service.generate_chat_response(
            user_id=self.user_general_bot.user_id,
            system_prompt_name='SYSTEM', user_prompt_name='USER', prompt_category='GENERAL_BOT', prompt_context={}
        )

        user_after_11th = User.objects.get(user_id=self.user_general_bot.user_id)
        self.assertEqual(user_after_11th.gpt_5_2_daily_count, 10) # Should not increment
        self.assertEqual(mock_create.call_args.kwargs['model'], 'gpt-5-mini') # Should fall back
