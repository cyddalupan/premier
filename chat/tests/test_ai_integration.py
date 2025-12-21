from django.test import TestCase
from unittest.mock import patch, MagicMock
from chat.models import User, Question, ExamResult, ChatLog
from chat.ai_integration import AIIntegration
from django.conf import settings
from chat.utils import get_prompt
import openai

# Mock settings for testing
settings.OPEN_AI_TOKEN = 'test_openai_token'


from django.test import TestCase
from unittest.mock import patch, MagicMock
from chat.models import User, Question, ExamResult, ChatLog
from chat.ai_integration import AIIntegration
from django.conf import settings
from chat.utils import get_prompt
import openai
from django.utils import timezone

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
        self.assertEqual(call_kwargs['messages'][0]['role'], 'system')
        self.assertEqual(call_kwargs['messages'][0]['content'], get_prompt(name='RE_ENGAGEMENT_SYSTEM_PROMPT', category='RE_ENGAGEMENT'))
        self.assertIn("friendly and highly creative AI assistant", call_kwargs['messages'][0]['content'])
        self.assertIn("Your primary goal is to effectively re-engage inactive users with personalized, compelling, and varied messages.", call_kwargs['messages'][0]['content'])
        self.assertIn("You have the discretion to choose the most appropriate type of re-engagement message", call_kwargs['messages'][0]['content'])
        
        self.assertEqual(call_kwargs['messages'][1]['role'], 'user')
        user_prompt_content = call_kwargs['messages'][1]['content']
        self.assertIn(self.user.first_name, user_prompt_content)
        self.assertIn(self.user.current_stage, user_prompt_content)
        self.assertIn(self.user.summary, user_prompt_content)
        self.assertIn(self.conversation_history, user_prompt_content)
        self.assertNotIn('message_type', user_prompt_content) # Ensure message_type is no longer in prompt

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
            # Assert that get_prompt was called for system and user prompts
            self.assertEqual(mock_get_prompt.call_count, 2)

            # Assert that the specific error message was logged
            self.assertTrue(any(
                "ERROR:chat.ai_integration:OpenAI API error during chat response generation: API Error Test Message for Chat Response" in log_entry
                for log_entry in cm.output
            ))


class TestUserStrengthAssessment(TestCase):
    def setUp(self):
        self.ai_integration_service = AIIntegration() # Instantiate AIIntegration locally for tests
        self.user_id = 'assessment_user_psid'
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name='AssessmentUser',
            current_stage='MOCK_EXAM',
            exam_question_counter=8 # User has completed the exam
        )

        self.q_criminal1 = Question.objects.create(category='Criminal Law', question_text='Crim Q1', expected_answer='Crim A1')
        self.q_criminal2 = Question.objects.create(category='Criminal Law', question_text='Crim Q2', expected_answer='Crim A2')
        self.q_civil1 = Question.objects.create(category='Civil Law', question_text='Civil Q1', expected_answer='Civil A1')
        self.q_civil2 = Question.objects.create(category='Civil Law', question_text='Civil Q2', expected_answer='Civil A2')
        self.q_labor1 = Question.objects.create(category='Labor Law', question_text='Labor Q1', expected_answer='Labor A1')
        self.q_labor2 = Question.objects.create(category='Labor Law', question_text='Labor Q2', expected_answer='Labor A2')
        self.q_tax1 = Question.objects.create(category='Tax Law', question_text='Tax Q1', expected_answer='Tax A1')
        self.q_tax2 = Question.objects.create(category='Tax Law', question_text='Tax Q2', expected_answer='Tax A2')

        # Simulate exam results with strengths in Criminal Law and Civil Law
        ExamResult.objects.create(user=self.user, question=self.q_criminal1, score=90)
        ExamResult.objects.create(user=self.user, question=self.q_criminal2, score=95)
        ExamResult.objects.create(user=self.user, question=self.q_civil1, score=88)
        ExamResult.objects.create(user=self.user, question=self.q_civil2, score=85)
        ExamResult.objects.create(user=self.user, question=self.q_labor1, score=60)
        ExamResult.objects.create(user=self.user, question=self.q_labor2, score=65)
        ExamResult.objects.create(user=self.user, question=self.q_tax1, score=50)
        ExamResult.objects.create(user=self.user, question=self.q_tax2, score=55)

    @patch('openai.chat.completions.create')
    @patch('chat.tasks.send_messenger_message') # This patch is not needed in test_ai_integration.py but was present in original
    def test_assessment_generation_with_strengths(self, mock_send_messenger_message, mock_create):
        # Mock the AI response for strength assessment
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
        
        # Verify the prompt sent to AI
        call_args, call_kwargs = mock_create.call_args
        self.assertIn('Criminal Law (Avg Score: 92.5)', call_kwargs['messages'][1]['content'])
        self.assertIn('Civil Law (Avg Score: 86.5)', call_kwargs['messages'][1]['content'])
        self.assertIn('Labor Law (Avg Score: 62.5)', call_kwargs['messages'][1]['content'])
        self.assertIn('Tax Law (Avg Score: 52.5)', call_kwargs['messages'][1]['content'])
        self.assertEqual(call_kwargs['model'], 'gpt-5.2')
        self.assertGreater(call_kwargs['max_completion_tokens'], 100) # Assessment should allow for more tokens

        # This mock is not relevant for this unit test and should ideally not be here.
        # However, to maintain the exact behavior of the original test as requested, it's kept.
        mock_send_messenger_message.assert_not_called() 

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error Test Message'))
    def test_assessment_generation_openai_error(self, mock_create):
        # Mock the AI response to throw an OpenAIError
        
        with self.assertLogs('chat', level='INFO') as cm:
            assessment_message = self.ai_integration_service.generate_strength_assessment(self.user)

            self.assertEqual(assessment_message, "I'm sorry, I couldn't generate your strength assessment at the moment. Please try again later.")
            mock_create.assert_called_once()
            
            call_args, call_kwargs = mock_create.call_args
            self.assertIn("You are a highly analytical and encouraging AI assistant for a Law Review Center.", call_kwargs['messages'][0]['content'])
            self.assertIn("A student has completed a mock bar exam. Here is their performance aggregated by legal category:", call_kwargs['messages'][1]['content'])
            self.assertIn("- Criminal Law (Avg Score: 92.5)", call_kwargs['messages'][1]['content'])
            self.assertIn("- Civil Law (Avg Score: 86.5)", call_kwargs['messages'][1]['content'])
            self.assertIn("- Labor Law (Avg Score: 62.5)", call_kwargs['messages'][1]['content'])
            self.assertIn("- Tax Law (Avg Score: 52.5)", call_kwargs['messages'][1]['content'])

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

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
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], get_prompt(name='NAME_EXTRACTION_SYSTEM_PROMPT', category='NAME_EXTRACTION'))

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error'))
    def test_extract_name_openai_error_returns_none(self, mock_create):
        name = self.ai_integration_service.extract_name_from_message("My name is Test User.")
        self.assertEqual(name, 'User')
        mock_create.assert_called_once()