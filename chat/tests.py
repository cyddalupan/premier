from django.test import TestCase
from unittest.mock import patch, MagicMock
import unittest.mock as mock
from datetime import datetime, timedelta
from freezegun import freeze_time
from chat.models import User, ChatLog, Question
from chat.tasks import process_messenger_message, check_inactive_users, RE_ENGAGEMENT_MESSAGE_TYPES # Import check_inactive_users
from chat.utils import ai_integration_service # Import ai_integration_service
from django.conf import settings
from django.utils import timezone # Import timezone utilities
from chat import prompts # Import prompts

import openai # Import openai to mock its errors


# Mock settings for testing
settings.MESSENGER_VERIFY_TOKEN = 'test_verify_token'
settings.OPEN_AI_TOKEN = 'test_openai_token'


class TestAIIntegration(TestCase):
    def setUp(self):
        self.user_id = 'test_user_ai'
        self.user_stage = 'MARKETING'
        self.user_summary = 'User is interested in mock exams and needs motivation.'

    @patch('openai.chat.completions.create')
    def test_generate_re_engagement_message_success(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='AI-composed re-engagement message!')
                    )
                )
            )]
        )

        message = ai_integration_service.generate_re_engagement_message(
            user_id=self.user_id,
            current_stage=self.user_stage,
            user_summary=self.user_summary,
            message_type='Trivia/Fun Fact' # Example message type
        )

        self.assertEqual(message, 'AI-composed re-engagement message!')
        mock_create.assert_called_once()
        call_args, call_kwargs = mock_create.call_args
        self.assertEqual(call_kwargs['model'], 'gpt-5-mini')
        self.assertEqual(call_kwargs['messages'][0]['role'], 'system')
        self.assertEqual(call_kwargs['messages'][0]['content'], prompts.RE_ENGAGEMENT_SYSTEM_PROMPT)
        self.assertIn("Ensure your messages are easy to read on Messenger by using proper spacing", call_kwargs['messages'][0]['content'])
        self.assertIn("Use relevant, subtle, guiding emojis", call_kwargs['messages'][0]['content'])
        self.assertEqual(call_kwargs['messages'][1]['role'], 'user')
        self.assertIn(self.user_stage, call_kwargs['messages'][1]['content'])
        self.assertIn(self.user_summary, call_kwargs['messages'][1]['content'])
        self.assertIn('Trivia/Fun Fact', call_kwargs['messages'][1]['content'])
        self.assertEqual(call_kwargs['max_tokens'], 100)

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error'))
    def test_generate_re_engagement_message_openai_error_fallback(self, mock_create):
        message = ai_integration_service.generate_re_engagement_message(
            user_id=self.user_id,
            current_stage=self.user_stage,
            user_summary=self.user_summary,
            message_type='Trivia/Fun Fact' # Example message type
        )
        self.assertEqual(message, 'Hello! We missed you. How can I help you today?')
        mock_create.assert_called_once()

    @patch('openai.chat.completions.create', side_effect=Exception('Generic Error'))
    def test_generate_re_engagement_message_generic_error_fallback(self, mock_create):
        message = ai_integration_service.generate_re_engagement_message(
            user_id=self.user_id,
            current_stage=self.user_stage,
            user_summary=self.user_summary,
            message_type='Trivia/Fun Fact' # Example message type
        )
        self.assertEqual(message, 'Hi there! Just checking in. Let me know if you have any questions.')
        mock_create.assert_called_once()


class TestReEngagementCron(TestCase):
    def setUp(self):
        self.now = timezone.make_aware(datetime(2025, 1, 1, 12, 0, 0))
        
        # User active 1 hour ago - should NOT be re-engaged
        self.active_user = User.objects.create(
            user_id='active_user_1',
            first_name='Active',
            current_stage='GENERAL_BOT',
            last_interaction_timestamp=self.now - timedelta(hours=1),
            summary='Active user summary.',
            re_engagement_stage_index=0,
            last_re_engagement_message_sent_at=None
        )

        # User inactive 21.5 hours ago, ready for stage 4 re-engagement
        self.inactive_user_general = User.objects.create(
            user_id='inactive_user_general_1',
            first_name='InactiveGeneral',
            current_stage='GENERAL_BOT',
            last_interaction_timestamp=self.now - timedelta(hours=21, minutes=30),
            summary='Inactive general bot user summary.',
            re_engagement_stage_index=3, # Ready for stage 4
            last_re_engagement_message_sent_at=None
        )

        # User inactive 21.75 hours ago, ready for stage 4 re-engagement
        self.inactive_user_marketing = User.objects.create(
            user_id='inactive_user_marketing_1',
            first_name='InactiveMarketing',
            current_stage='MARKETING',
            last_interaction_timestamp=self.now - timedelta(hours=21, minutes=45),
            summary='Inactive marketing user summary.',
            re_engagement_stage_index=3, # Ready for stage 4
            last_re_engagement_message_sent_at=None
        )

        # User inactive 48 hours ago, in MOCK_EXAM stage - should NOT be re-engaged
        self.inactive_user_mock_exam = User.objects.create(
            user_id='inactive_user_mock_exam_1',
            first_name='InactiveMockExam',
            current_stage='MOCK_EXAM',
            last_interaction_timestamp=self.now - timedelta(hours=48),
            summary='Inactive mock exam user summary.',
            re_engagement_stage_index=0,
            last_re_engagement_message_sent_at=None
        )

        # User with no interaction timestamp
        self.user_no_timestamp = User.objects.create(
            user_id='user_no_timestamp_1',
            first_name='NoTimestamp',
            current_stage='ONBOARDING',
            last_interaction_timestamp=None,
            summary='User with no timestamp.',
            re_engagement_stage_index=0,
            last_re_engagement_message_sent_at=None
        )


    @freeze_time('2025-01-01 12:00:00') # Fixed time for test execution
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.generate_re_engagement_message', return_value='AI-composed re-engagement message!')
    def test_check_inactive_users_re_engages_correct_users(self, mock_generate_message, mock_send_message):
        # With the new logic, the old 'inactive' users (25h, 30h) will now fall into stage 4 (21-22h)
        # Assuming they haven't received any messages yet.
        # This test needs to be adjusted. Since the old structure relies on fixed 24h+ inactivity,
        # and the new logic uses stages, this test will pass only if it covers stage 4.
        # We will assume that these users, being 25h and 30h inactive, fall into stage 4.
        


        check_inactive_users()

        # Assert that generate_re_engagement_message was called for the correct users (2 times for the two inactive users)
        self.assertEqual(mock_generate_message.call_count, 2)
        mock_generate_message.assert_any_call(
            user_id=self.inactive_user_general.user_id,
            current_stage=self.inactive_user_general.current_stage,
            user_summary=self.inactive_user_general.summary,
            message_type=mock.ANY # Accept any message_type
        )
        mock_generate_message.assert_any_call(
            user_id=self.inactive_user_marketing.user_id,
            current_stage=self.inactive_user_marketing.current_stage,
            user_summary=self.inactive_user_marketing.summary,
            message_type=mock.ANY # Accept any message_type
        )

        # Ensure it was NOT called for active or mock_exam users
        called_user_ids = [c.kwargs['user_id'] for c in mock_generate_message.call_args_list]
        self.assertNotIn(self.active_user.user_id, called_user_ids)
        self.assertNotIn(self.inactive_user_mock_exam.user_id, called_user_ids)


        # Assert that send_messenger_message was called for the correct users (2 times)
        self.assertEqual(mock_send_message.call_count, 2)
        mock_send_message.assert_any_call(self.inactive_user_general.user_id, 'AI-composed re-engagement message!')
        mock_send_message.assert_any_call(self.inactive_user_marketing.user_id, 'AI-composed re-engagement message!')
        
        # Verify user state is updated
        self.inactive_user_general.refresh_from_db()
        self.assertEqual(self.inactive_user_general.re_engagement_stage_index, 4) # Should have moved to stage 4
        self.assertIsNotNone(self.inactive_user_general.last_re_engagement_message_sent_at)
        self.inactive_user_marketing.refresh_from_db()
        self.assertEqual(self.inactive_user_marketing.re_engagement_stage_index, 4) # Should have moved to stage 4
        self.assertIsNotNone(self.inactive_user_marketing.last_re_engagement_message_sent_at)


        # Verify last_interaction_timestamp is NOT updated by re-engagement messages
        self.assertEqual(self.inactive_user_general.last_interaction_timestamp, self.now - timedelta(hours=21, minutes=30))
        self.assertEqual(self.inactive_user_marketing.last_interaction_timestamp, self.now - timedelta(hours=21, minutes=45))
        
        # Verify non-re-engaged users remain unchanged
        self.active_user.refresh_from_db()
        self.assertEqual(self.active_user.last_interaction_timestamp, self.now - timedelta(hours=1))
        self.inactive_user_mock_exam.refresh_from_db()
        self.assertEqual(self.inactive_user_mock_exam.last_interaction_timestamp, self.now - timedelta(hours=48))
        self.user_no_timestamp.refresh_from_db()
        self.assertIsNone(self.user_no_timestamp.last_interaction_timestamp)


    @freeze_time('2025-01-01 12:00:00')
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.generate_re_engagement_message', return_value='AI-composed re-engagement message!')
    @patch('random.choice', side_effect=lambda x: x[0])
    def test_check_inactive_users_calls_with_random_message_type(self, mock_random_choice, mock_generate_message, mock_send_message):


        check_inactive_users()

        mock_random_choice.assert_called_with(RE_ENGAGEMENT_MESSAGE_TYPES)
        self.assertEqual(mock_generate_message.call_count, 2)
        
        expected_message_type = RE_ENGAGEMENT_MESSAGE_TYPES[0]
        
        mock_generate_message.assert_any_call(
            user_id=self.inactive_user_general.user_id,
            current_stage=self.inactive_user_general.current_stage,
            user_summary=self.inactive_user_general.summary,
            message_type=expected_message_type
        )
        mock_generate_message.assert_any_call(
            user_id=self.inactive_user_marketing.user_id,
            current_stage=self.inactive_user_marketing.current_stage,
            user_summary=self.inactive_user_marketing.summary,
            message_type=expected_message_type
        )


    @freeze_time('2025-01-01 12:00:00')
    @patch('chat.tasks.ChatLog.objects.create')
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.generate_re_engagement_message')
    def test_check_inactive_users_no_inactive_users(self, mock_generate_message, mock_send_message, mock_chat_log_create):
        # All users are active for new logic (within 1 hour of now)
        self.inactive_user_general.last_interaction_timestamp = self.now - timedelta(minutes=59)
        self.inactive_user_general.re_engagement_stage_index = 0 # Reset for this test
        self.inactive_user_general.save()
        self.inactive_user_marketing.last_interaction_timestamp = self.now - timedelta(minutes=50)
        self.inactive_user_marketing.re_engagement_stage_index = 0 # Reset for this test
        self.inactive_user_marketing.save()

        check_inactive_users()

        mock_generate_message.assert_not_called()
        mock_send_message.assert_not_called()
        mock_chat_log_create.assert_not_called()

        # Ensure timestamps and re-engagement stages remain unchanged
        self.active_user.refresh_from_db()
        self.assertEqual(self.active_user.last_interaction_timestamp, self.now - timedelta(hours=1))
        self.assertEqual(self.active_user.re_engagement_stage_index, 0)
        self.assertIsNone(self.active_user.last_re_engagement_message_sent_at)
        
        self.inactive_user_general.refresh_from_db()
        self.assertEqual(self.inactive_user_general.last_interaction_timestamp, self.now - timedelta(minutes=59))
        self.assertEqual(self.inactive_user_general.re_engagement_stage_index, 0)
        self.assertIsNone(self.inactive_user_general.last_re_engagement_message_sent_at)

        self.inactive_user_marketing.refresh_from_db()
        self.assertEqual(self.inactive_user_marketing.last_interaction_timestamp, self.now - timedelta(minutes=50))
        self.assertEqual(self.inactive_user_marketing.re_engagement_stage_index, 0)
        self.assertIsNone(self.inactive_user_marketing.last_re_engagement_message_sent_at)

        self.inactive_user_mock_exam.refresh_from_db()
        self.assertEqual(self.inactive_user_mock_exam.last_interaction_timestamp, self.now - timedelta(hours=48))
        self.user_no_timestamp.refresh_from_db()
        self.assertIsNone(self.user_no_timestamp.last_interaction_timestamp)

    RE_ENGAGEMENT_INTERVALS = [
        (1, 2),
        (5, 6),
        (11, 12),
        (21, 22),
    ]

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.tasks.ChatLog.objects.create')
    @patch('chat.utils.ai_integration_service.generate_re_engagement_message')
    @patch('random.choice', side_effect=lambda x: x[0]) # Mock random.choice to always pick the first element
    @patch('chat.tasks.User.objects.filter') # Patch User.objects.filter
    def test_multi_stage_re_engagement_flow(self, mock_user_filter, mock_random_choice, mock_generate_message, mock_chat_log_create, mock_send_message):
        user = User.objects.create(
            user_id='multi_stage_user_1',
            first_name='MultiStage',
            current_stage='GENERAL_BOT',
            last_interaction_timestamp=self.now - timedelta(minutes=30), # User interacted 30 mins ago
            summary='User for multi-stage re-engagement.',
            re_engagement_stage_index=0,
            last_re_engagement_message_sent_at=None
        )
        # Configure the mock filter to return only our test user
        mock_user_filter.return_value = [user] # Directly return the list of users

        initial_interaction_time = user.last_interaction_timestamp
        
        mock_generate_message.return_value = 'Re-engagement message AI content'

        # --- Test 1: Stage 1: 1 hour 30 minutes (within 1-2 hour window), should trigger if user interacted 30 mins ago ---
        with freeze_time(initial_interaction_time + timedelta(hours=1, minutes=30)): # Current time becomes 1h 30m after initial interaction (i.e., user is 1h inactive)
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 1)
            mock_send_message.assert_called_once_with(user.user_id, 'Re-engagement message AI content')
            self.assertEqual(mock_generate_message.call_count, 1)
            mock_generate_message.assert_called_once()
            self.assertEqual(mock_chat_log_create.call_count, 1)
            mock_chat_log_create.assert_called_once_with(
                user=user,
                sender_type='SYSTEM_AI',
                message_content='Re-engagement message AI content'
            )
            self.assertEqual(user.re_engagement_stage_index, 1) # Should move to stage 1
            self.assertEqual(user.last_interaction_timestamp, initial_interaction_time) # Should NOT be updated by bot-initiated message
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()
        new_last_interaction_time = user.last_interaction_timestamp

        # --- Test 2: Still within Stage 1's *interval*, but message already sent and last_interaction_timestamp updated ---
        # The user's last_interaction_timestamp is now `new_last_interaction_time` (which is 1h30m after initial)
        # We need to check a point within (new_last_interaction_time + 1min) for example, where overall inactivity is still within (1,2]
        # But `re_engagement_stage_index` is already 1, so no new message should be sent.
        with freeze_time(new_last_interaction_time + timedelta(minutes=10)):
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_generate_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 1) # Should remain 1
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time) # Should not be updated
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()


        # --- Test 3: Passed Stage 1, but still before Stage 2 ---
        with freeze_time(initial_interaction_time + timedelta(hours=3)):
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 1) # Should remain 1
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time) # Should not be updated
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()


        # --- Test 4: Passed Stage 1, but still before Stage 2 ---
        with freeze_time(initial_interaction_time + timedelta(hours=3)):
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 1) # Should remain 1
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time) # Should not be updated
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()


        # --- Test 5: Stage 2: 5 hours 30 minutes (within 5-6 hour window) ---
        with freeze_time(initial_interaction_time + timedelta(hours=5, minutes=30)):
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 1)
            mock_send_message.assert_called_once_with(user.user_id, 'Re-engagement message AI content')
            self.assertEqual(mock_generate_message.call_count, 1)
            self.assertEqual(mock_chat_log_create.call_count, 1)
            self.assertEqual(user.re_engagement_stage_index, 2)
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time)
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()
        new_last_interaction_time = user.last_interaction_timestamp


        # --- Test 6: Stage 3: 11 hours 45 minutes (within 11-12 hour window) ---
        with freeze_time(initial_interaction_time + timedelta(hours=11, minutes=45)):
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 1)
            mock_send_message.assert_called_once_with(user.user_id, 'Re-engagement message AI content')
            self.assertEqual(mock_generate_message.call_count, 1)
            self.assertEqual(mock_chat_log_create.call_count, 1)
            self.assertEqual(user.re_engagement_stage_index, 3)
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time)
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()
        new_last_interaction_time = user.last_interaction_timestamp


        # --- Test 7: Stage 4: 21 hours 15 minutes (within 21-22 hour window) ---
        with freeze_time(initial_interaction_time + timedelta(hours=21, minutes=15)):
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 1)
            mock_send_message.assert_called_once_with(user.user_id, 'Re-engagement message AI content')
            self.assertEqual(mock_generate_message.call_count, 1)
            self.assertEqual(mock_chat_log_create.call_count, 1)
            self.assertEqual(user.re_engagement_stage_index, 4)
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time)
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()
        last_re_engagement_time = user.last_interaction_timestamp


        # --- Test 8: After all stages: 25 hours (no more re-engagement from this flow) ---
        with freeze_time(initial_interaction_time + timedelta(hours=25)):
            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_generate_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 4) # Should remain 4
            self.assertEqual(user.last_interaction_timestamp, last_re_engagement_time) # Should not be updated
        mock_send_message.reset_mock()
        mock_generate_message.reset_mock()
        mock_chat_log_create.reset_mock()


        # --- Test 9: User has a new interaction after all re-engagement stages ---
        # This should reset the re-engagement stage for the user to 0
        user.last_interaction_timestamp = initial_interaction_time + timedelta(days=2) # Simulate new interaction, well after previous one
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.re_engagement_stage_index, 4) # Still 4 before new activity resets it

        # Simulate a user message to trigger reset logic in process_messenger_message
        user_message_event = {
            'sender': {'id': user.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_new_interaction', 'text': 'Hello again!'},
            'timestamp': int((user.last_interaction_timestamp + timedelta(minutes=1)).timestamp() * 1000)
        }
        process_messenger_message(user_message_event) # This will reset re_engagement_stage_index

        user.refresh_from_db()
        self.assertEqual(user.re_engagement_stage_index, 0) # Expect stage to reset to 0 because of new activity
        # Last interaction timestamp should be updated by process_messenger_message
        self.assertGreater(user.last_interaction_timestamp, initial_interaction_time + timedelta(days=2))


class MockExamStageTest(TestCase):
    def setUp(self):
        self.user_id = 'mock_exam_user_psid'
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name='ExamTaker',
            current_stage='MOCK_EXAM',
            exam_question_counter=0
        )
        self.q1 = Question.objects.create(
            category='Criminal Law',
            question_text='Question 1 text?',
            expected_answer='Answer 1'
        )
        self.q2 = Question.objects.create(
            category='Civil Law',
            question_text='Question 2 text?',
            expected_answer='Answer 2'
        )

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.mock_exam.get_random_exam_question') # Patch where it's used
    @patch('chat.stages.mock_exam.ai_integration_service.grade_exam_answer') # Patch where it's used
    def test_start_exam_sends_first_question(self, mock_grade_exam_answer, mock_get_random_exam_question, mock_send_messenger_message):
        mock_get_random_exam_question.return_value = self.q1

        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_start', 'text': 'start'}, # User starting exam
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        mock_get_random_exam_question.assert_called_once()
        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user_id)
        # FIX: Expected counter should be 1, as it's incremented before message composition
        self.assertEqual(args[1], f'Alright, {self.user.first_name}! Here is your first mock exam question (1/8):\n\n{self.q1.question_text}')

        self.user.refresh_from_db()
        self.assertEqual(self.user.exam_question_counter, 1)
        self.assertEqual(self.user.current_stage, 'MOCK_EXAM')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.mock_exam.get_random_exam_question') # Patch where it's used
    @patch('chat.stages.mock_exam.ai_integration_service.grade_exam_answer') # Patch where it's used
    def test_submit_answer_and_get_next_question(self, mock_grade_exam_answer, mock_get_random_exam_question, mock_send_messenger_message):
        # Set user's state to be in the middle of an exam
        self.user.exam_question_counter = 1
        self.user.last_question_id_asked = self.q1 # Set the last asked question
        self.user.save()

        # Mock what the AI grading service returns - FIX: Changed key from grammar_syntax_feedback to grammar_feedback
        mock_grade_exam_answer.return_value = {
            'legal_writing_feedback': 'Good legal writing.',
            'legal_basis_feedback': 'Relevant laws cited.',
            'application_feedback': 'Applied well.',
            'conclusion_feedback': 'Clear conclusion.',
            'score': 85
        }
        # Mock what get_random_exam_question returns for grading and next question
        mock_get_random_exam_question.return_value = self.q2 # Will be called for the *next* question

        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_answer1', 'text': 'My answer for Q1'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect two calls to send_messenger_message: feedback and next question
        self.assertEqual(mock_send_messenger_message.call_count, 2)
        mock_grade_exam_answer.assert_called_once_with(
            user_id=self.user.user_id,
            question_text=self.q1.question_text,
            user_answer=user_message_event['message']['text'],
            expected_answer=self.q1.expected_answer
        )

        # Verify feedback message
        feedback_args, feedback_kwargs = mock_send_messenger_message.call_args_list[0]
        self.assertEqual(feedback_args[0], self.user_id)
        expected_feedback_msg = 'Here\'s the feedback on your answer:\n- Legal Writing: Good legal writing.\n- Legal Basis: Relevant laws cited.\n- Application: Applied well.\n- Conclusion: Clear conclusion.\nYour score: 85/100\n'
        self.assertEqual(feedback_args[1], expected_feedback_msg)

        # Verify next question message
        next_q_args, next_q_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(next_q_args[0], self.user_id)
        self.assertEqual(next_q_args[1], f'Next question (2/8):\n\n{self.q2.question_text}')

        self.user.refresh_from_db()
        self.assertEqual(self.user.exam_question_counter, 2)
        self.assertEqual(self.user.current_stage, 'MOCK_EXAM')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.mock_exam.get_random_exam_question') # Patch where it's used
    @patch('chat.stages.mock_exam.ai_integration_service.grade_exam_answer') # Patch where it's used
    @patch('chat.stages.mock_exam.ai_integration_service.generate_strength_assessment') # New patch for assessment
    def test_complete_exam_and_transition_to_general_bot(self, mock_generate_strength_assessment, mock_grade_exam_answer, mock_get_random_exam_question, mock_send_messenger_message):
        # Set user's state to be on the last question
        self.user.exam_question_counter = 8
        self.user.last_question_id_asked = self.q1 # Set the last asked question
        self.user.save()

        # Mock what the AI grading service returns - FIX: Changed key from grammar_syntax_feedback to grammar_feedback
        mock_grade_exam_answer.return_value = {
            'legal_writing_feedback': 'Good legal writing.',
            'legal_basis_feedback': 'Relevant laws cited.',
            'application_feedback': 'Applied well.',
            'conclusion_feedback': 'Clear conclusion.',
            'score': 90
        }
        mock_get_random_exam_question.return_value = None # No more questions after the last one
        
        mock_assessment_message = 'Based on your performance, you demonstrated strong aptitude in Criminal Law.'
        mock_generate_strength_assessment.return_value = mock_assessment_message

        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_answer8', 'text': 'My final answer'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expected calls: feedback, completion message, assessment message, and two persuasion messages (for unregistered user by default)
        self.assertEqual(mock_send_messenger_message.call_count, 5)
        mock_grade_exam_answer.assert_called_once()
        mock_generate_strength_assessment.assert_called_once_with(self.user)

        # Verify feedback message
        feedback_args, feedback_kwargs = mock_send_messenger_message.call_args_list[0]
        self.assertEqual(feedback_args[0], self.user_id)
        expected_feedback_msg = 'Here\'s the feedback on your answer:\n- Legal Writing: Good legal writing.\n- Legal Basis: Relevant laws cited.\n- Application: Applied well.\n- Conclusion: Clear conclusion.\nYour score: 90/100\n'
        self.assertEqual(feedback_args[1], expected_feedback_msg)

        # Verify completion message
        completion_args, completion_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(completion_args[0], self.user_id)
        self.assertEqual(completion_args[1], 'You have completed all 8 mock exam questions! Great job!')

        # Verify strength assessment message
        assessment_args, assessment_kwargs = mock_send_messenger_message.call_args_list[2]
        self.assertEqual(assessment_args[0], self.user_id)
        self.assertEqual(assessment_args[1], mock_assessment_message)

        # Verify persuasion messages (calls 3 and 4 in 0-indexed list)
        persuasion_call1_args, _ = mock_send_messenger_message.call_args_list[3]
        self.assertIn('Congratulations on completing the mock exam, ExamTaker!', persuasion_call1_args[1])
        persuasion_call2_args, _ = mock_send_messenger_message.call_args_list[4]
        self.assertIn('It\'s the best way to prepare for the bar exam!', persuasion_call2_args[1])

        # Verify assessment message was logged to ChatLog
        chat_log = ChatLog.objects.filter(
            user=self.user,
            sender_type='SYSTEM_AI',
            message_content=mock_assessment_message
        ).first()
        self.assertIsNotNone(chat_log, 'Strength assessment message was not logged.')

        self.user.refresh_from_db()
        self.assertEqual(self.user.exam_question_counter, 0)
        self.assertEqual(self.user.current_stage, 'GENERAL_BOT')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.mock_exam.get_random_exam_question') # Patch where it's used
    def test_no_questions_available_at_start(self, mock_get_random_exam_question, mock_send_messenger_message):
        mock_get_random_exam_question.return_value = None # Simulate no questions

        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_start_no_q', 'text': 'start'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user.user_id)
        self.assertEqual(args[1], 'I\'m sorry, I couldn\'t find any exam questions at the moment. Please try again later.')

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'GENERAL_BOT') # Should transition out
        self.assertEqual(self.user.exam_question_counter, 0)


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
    @patch('chat.utils.ai_integration_service.get_quick_reply') # Patch the method directly
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



class TestUserStrengthAssessment(TestCase):
    def setUp(self):
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
        from chat.models import ExamResult
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

        from chat.utils import ai_integration_service
        assessment_message = ai_integration_service.generate_strength_assessment(self.user)

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

        # Simulate the integration of this assessment into the message flow (this part will be in mock_exam.py)
        # For now, just test that if called, send_messenger_message would send it.
        mock_send_messenger_message.assert_not_called() # Should not be called by generate_strength_assessment directly

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error Test Message'))
    def test_assessment_generation_openai_error(self, mock_create):
        # Mock the AI response to throw an OpenAIError
        from chat.utils import ai_integration_service
        
        with self.assertLogs('chat', level='INFO') as cm:
            assessment_message = ai_integration_service.generate_strength_assessment(self.user)

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
        self.ai_integration_service = ai_integration_service

    @patch('openai.chat.completions.create')
    def test_extract_name_from_simple_message(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='John Doe')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("My name is John Doe.")
        self.assertEqual(name, 'John Doe')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'My name is John Doe.'")
        self.assertEqual(mock_create.call_args.kwargs['messages'][0]['content'], prompts.NAME_EXTRACTION_SYSTEM_PROMPT)

    @patch('openai.chat.completions.create')
    def test_extract_name_from_complex_message(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='Jane Smith')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("Hello, I am Jane Smith, a law student.")
        self.assertEqual(name, 'Jane Smith')
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'Hello, I am Jane Smith, a law student.'")

    @patch('openai.chat.completions.create')
    def test_extract_name_no_name_found(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='None')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("I am interested in legal writing.")
        self.assertIsNone(name)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: 'I am interested in legal writing.'")

    @patch('openai.chat.completions.create')
    def test_extract_name_empty_message(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content=MagicMock(
                        strip=MagicMock(return_value='None')
                    )
                )
            )]
        )
        name = self.ai_integration_service.extract_name_from_message("")
        self.assertIsNone(name)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.kwargs['messages'][1]['content'], "Extract the name from the following text: ''")

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError('API Error'))
    def test_extract_name_openai_error_returns_none(self, mock_create):
        name = self.ai_integration_service.extract_name_from_message("My name is Test User.")
        self.assertIsNone(name)
        mock_create.assert_called_once()
    

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
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_ai_response_logged_as_system_ai(self, mock_get_quick_reply, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_unregistered.exam_question_counter = -1
        self.user_unregistered.save()

        mock_ai_response = 'This is a mocked AI quick reply.'
        mock_get_quick_reply.return_value = mock_ai_response

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
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_initial_general_bot_persuasion_unregistered_user(self, mock_get_quick_reply, mock_send_messenger_message):
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
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_initial_general_bot_persuasion_registered_user(self, mock_get_quick_reply, mock_send_messenger_message):
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
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_general_bot_fallback_persuasion_unregistered_user(self, mock_get_quick_reply, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_unregistered.exam_question_counter = -1
        self.user_unregistered.save()

        mock_get_quick_reply.return_value = None # Simulate AI fallback

        user_message_event = {
            'sender': {'id': self.user_unregistered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_fallback_unreg', 'text': 'gibberish'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect 3 messages: fallback, 2 persuasion
        self.assertEqual(mock_send_messenger_message.call_count, 3)
        
        call_list = mock_send_messenger_message.call_args_list

        # Check fallback message
        self.assertIn("I'm sorry, I couldn't process that query at the moment. Can you please rephrase?", call_list[0].args[1])
        
        # Check persuasion messages
        self.assertIn("Are you looking for more resources or detailed explanations, GeneralBotUnregUser?", call_list[1].args[1])
        self.assertIn("It's a powerful tool to enhance your bar exam preparation!", call_list[2].args[1])

        self.user_unregistered.refresh_from_db()
        self.assertEqual(self.user_unregistered.current_stage, 'GENERAL_BOT')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_general_bot_fallback_no_persuasion_registered_user(self, mock_get_quick_reply, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_registered.exam_question_counter = -1
        self.user_registered.save()

        mock_get_quick_reply.return_value = None # Simulate AI fallback

        user_message_event = {
            'sender': {'id': self.user_registered.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_fallback_reg', 'text': 'unknown query'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect 1 message: only fallback, no persuasion
        self.assertEqual(mock_send_messenger_message.call_count, 1)
        
        call_list = mock_send_messenger_message.call_args_list

        # Check fallback message
        self.assertIn("I'm sorry, I couldn't process that query at the moment. Can you please rephrase?", call_list[0].args[1])
        
        self.user_registered.refresh_from_db()
        self.assertEqual(self.user_registered.current_stage, 'GENERAL_BOT')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_general_bot_normal_ai_response_no_persuasion(self, mock_get_quick_reply, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user_unregistered.exam_question_counter = -1
        self.user_unregistered.save()

        mock_ai_response = "Here is a helpful response to your query."
        mock_get_quick_reply.return_value = mock_ai_response

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
