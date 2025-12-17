from django.test import TestCase
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from freezegun import freeze_time
from chat.models import User, ChatLog, Question
from chat.tasks import process_messenger_message, check_inactive_users # Import check_inactive_users
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
            choices=[MagicMock(message=MagicMock(content="AI-composed re-engagement message!"))]
        )

        message = ai_integration_service.generate_re_engagement_message(
            user_id=self.user_id,
            current_stage=self.user_stage,
            user_summary=self.user_summary
        )

        self.assertEqual(message, "AI-composed re-engagement message!")
        mock_create.assert_called_once()
        call_args, call_kwargs = mock_create.call_args
        self.assertEqual(call_kwargs['model'], "gpt-5-mini")
        self.assertEqual(call_kwargs['messages'][0]['role'], "system")
        self.assertEqual(call_kwargs['messages'][0]['content'], prompts.RE_ENGAGEMENT_SYSTEM_PROMPT)
        self.assertEqual(call_kwargs['messages'][1]['role'], "user")
        self.assertIn(self.user_stage, call_kwargs['messages'][1]['content'])
        self.assertIn(self.user_summary, call_kwargs['messages'][1]['content'])
        self.assertEqual(call_kwargs['max_tokens'], 100)
        self.assertEqual(call_kwargs['temperature'], 0.8)

    @patch('openai.chat.completions.create', side_effect=openai.OpenAIError("API Error"))
    def test_generate_re_engagement_message_openai_error_fallback(self, mock_create):
        message = ai_integration_service.generate_re_engagement_message(
            user_id=self.user_id,
            current_stage=self.user_stage,
            user_summary=self.user_summary
        )
        self.assertEqual(message, "Hello! We missed you. How can I help you today?")
        mock_create.assert_called_once()

    @patch('openai.chat.completions.create', side_effect=Exception("Generic Error"))
    def test_generate_re_engagement_message_generic_error_fallback(self, mock_create):
        message = ai_integration_service.generate_re_engagement_message(
            user_id=self.user_id,
            current_stage=self.user_stage,
            user_summary=self.user_summary
        )
        self.assertEqual(message, "Hi there! Just checking in. Let me know if you have any questions.")
        mock_create.assert_called_once()


class TestReEngagementCron(TestCase):
    def setUp(self):
        self.now = timezone.make_aware(datetime(2025, 1, 1, 12, 0, 0))
        self.inactive_threshold_hours = 24
        
        # User active 1 hour ago - should NOT be re-engaged
        self.active_user = User.objects.create(
            user_id='active_user_1',
            first_name='Active',
            current_stage='GENERAL_BOT',
            last_interaction_timestamp=self.now - timedelta(hours=1),
            summary='Active user summary.'
        )

        # User inactive 25 hours ago - should be re-engaged
        self.inactive_user_general = User.objects.create(
            user_id='inactive_user_general_1',
            first_name='InactiveGeneral',
            current_stage='GENERAL_BOT',
            last_interaction_timestamp=self.now - timedelta(hours=25),
            summary='Inactive general bot user summary.'
        )

        # User inactive 30 hours ago, in MARKETING stage - should be re-engaged
        self.inactive_user_marketing = User.objects.create(
            user_id='inactive_user_marketing_1',
            first_name='InactiveMarketing',
            current_stage='MARKETING',
            last_interaction_timestamp=self.now - timedelta(hours=30),
            summary='Inactive marketing user summary.'
        )

        # User inactive 48 hours ago, in MOCK_EXAM stage - should NOT be re-engaged
        self.inactive_user_mock_exam = User.objects.create(
            user_id='inactive_user_mock_exam_1',
            first_name='InactiveMockExam',
            current_stage='MOCK_EXAM',
            last_interaction_timestamp=self.now - timedelta(hours=48),
            summary='Inactive mock exam user summary.'
        )

        # User with no interaction timestamp (e.g., brand new, or pre-existing before feature)
        # Should NOT be re-engaged by this specific task, as last_interaction_timestamp__lt would exclude it
        self.user_no_timestamp = User.objects.create(
            user_id='user_no_timestamp_1',
            first_name='NoTimestamp',
            current_stage='ONBOARDING',
            last_interaction_timestamp=None,
            summary='User with no timestamp.'
        )

    @freeze_time('2025-01-01 12:00:00') # Fixed time for test execution
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.generate_re_engagement_message')
    def test_check_inactive_users_re_engages_correct_users(self, mock_generate_message, mock_send_message):
        mock_generate_message.side_effect = [
            "AI message for inactive_user_general!",
            "AI message for inactive_user_marketing!"
        ]

        check_inactive_users()

        # Assert that generate_re_engagement_message was called for the correct users
        self.assertEqual(mock_generate_message.call_count, 2)
        mock_generate_message.assert_any_call(
            user_id=self.inactive_user_general.user_id,
            current_stage=self.inactive_user_general.current_stage,
            user_summary=self.inactive_user_general.summary
        )
        mock_generate_message.assert_any_call(
            user_id=self.inactive_user_marketing.user_id,
            current_stage=self.inactive_user_marketing.current_stage,
            user_summary=self.inactive_user_marketing.summary
        )
        # Ensure it was NOT called for active or mock_exam users
        self.assertNotIn(
            (self.active_user.user_id, self.active_user.current_stage, self.active_user.summary),
            [c.args for c in mock_generate_message.call_args_list]
        )
        self.assertNotIn(
            (self.inactive_user_mock_exam.user_id, self.inactive_user_mock_exam.current_stage, self.inactive_user_mock_exam.summary),
            [c.args for c in mock_generate_message.call_args_list]
        )

        # Assert that send_messenger_message was called for the correct users
        self.assertEqual(mock_send_message.call_count, 2)
        mock_send_message.assert_any_call(self.inactive_user_general.user_id, "AI message for inactive_user_general!")
        mock_send_message.assert_any_call(self.inactive_user_marketing.user_id, "AI message for inactive_user_marketing!")
        
        # Verify last_interaction_timestamp is updated for re-engaged users
        self.inactive_user_general.refresh_from_db()
        self.assertGreater(self.inactive_user_general.last_interaction_timestamp, self.now - timedelta(hours=25))
        self.inactive_user_marketing.refresh_from_db()
        self.assertGreater(self.inactive_user_marketing.last_interaction_timestamp, self.now - timedelta(hours=30))

        # Verify last_interaction_timestamp is NOT updated for non-re-engaged users
        self.active_user.refresh_from_db()
        self.assertEqual(self.active_user.last_interaction_timestamp, self.now - timedelta(hours=1))
        self.inactive_user_mock_exam.refresh_from_db()
        self.assertEqual(self.inactive_user_mock_exam.last_interaction_timestamp, self.now - timedelta(hours=48))
        self.user_no_timestamp.refresh_from_db()
        self.assertIsNone(self.user_no_timestamp.last_interaction_timestamp)


    @freeze_time('2025-01-01 12:00:00')
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.generate_re_engagement_message')
    def test_check_inactive_users_no_inactive_users(self, mock_generate_message, mock_send_message):
        # All users are active
        self.inactive_user_general.last_interaction_timestamp = self.now - timedelta(hours=10)
        self.inactive_user_general.save()
        self.inactive_user_marketing.last_interaction_timestamp = self.now - timedelta(hours=5)
        self.inactive_user_marketing.save()

        check_inactive_users()

        # Assert no calls were made to generate messages or send messages
        mock_generate_message.assert_not_called()
        mock_send_message.assert_not_called()

        # Ensure timestamps remain unchanged
        self.active_user.refresh_from_db()
        self.assertEqual(self.active_user.last_interaction_timestamp, self.now - timedelta(hours=1))
        self.inactive_user_general.refresh_from_db()
        self.assertEqual(self.inactive_user_general.last_interaction_timestamp, self.now - timedelta(hours=10))
        self.inactive_user_marketing.refresh_from_db()
        self.assertEqual(self.inactive_user_marketing.last_interaction_timestamp, self.now - timedelta(hours=5))
        self.inactive_user_mock_exam.refresh_from_db()
        self.assertEqual(self.inactive_user_mock_exam.last_interaction_timestamp, self.now - timedelta(hours=48))


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
            expected_answer='Answer 1',
            rubric_criteria='Rubric 1'
        )
        self.q2 = Question.objects.create(
            category='Civil Law',
            question_text='Question 2 text?',
            expected_answer='Answer 2',
            rubric_criteria='Rubric 2'
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
        self.assertEqual(args[1], f"Alright, {self.user.first_name}! Here is your first mock exam question (1/8):\n\n{self.q1.question_text}")

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
            'grammar_feedback': 'Good grammar.',
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
        mock_grade_exam_answer.assert_called_once()

        # Verify feedback message
        feedback_args, feedback_kwargs = mock_send_messenger_message.call_args_list[0]
        self.assertEqual(feedback_args[0], self.user_id)
        expected_feedback_msg = "Here's the feedback on your answer:\n- Grammar/Syntax: Good grammar.\n- Legal Basis: Relevant laws cited.\n- Application: Applied well.\n- Conclusion: Clear conclusion.\nYour score: 85/100\n"
        self.assertEqual(feedback_args[1], expected_feedback_msg)

        # Verify next question message
        next_q_args, next_q_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(next_q_args[0], self.user_id)
        self.assertEqual(next_q_args[1], f"Next question (2/8):\n\n{self.q2.question_text}")

        self.user.refresh_from_db()
        self.assertEqual(self.user.exam_question_counter, 2)
        self.assertEqual(self.user.current_stage, 'MOCK_EXAM')

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.mock_exam.get_random_exam_question') # Patch where it's used
    @patch('chat.stages.mock_exam.ai_integration_service.grade_exam_answer') # Patch where it's used
    def test_complete_exam_and_transition_to_general_bot(self, mock_grade_exam_answer, mock_get_random_exam_question, mock_send_messenger_message):
        # Set user's state to be on the last question
        self.user.exam_question_counter = 8
        self.user.last_question_id_asked = self.q1 # Set the last asked question
        self.user.save()

        # Mock what the AI grading service returns - FIX: Changed key from grammar_syntax_feedback to grammar_feedback
        mock_grade_exam_answer.return_value = {
            'grammar_feedback': 'Good grammar.',
            'legal_basis_feedback': 'Relevant laws cited.',
            'application_feedback': 'Applied well.',
            'conclusion_feedback': 'Clear conclusion.',
            'score': 90
        }
        mock_get_random_exam_question.return_value = None # No more questions after the last one

        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_answer8', 'text': 'My final answer'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect two calls to send_messenger_message: feedback and completion message
        self.assertEqual(mock_send_messenger_message.call_count, 2)
        mock_grade_exam_answer.assert_called_once()

        # Verify feedback message
        feedback_args, feedback_kwargs = mock_send_messenger_message.call_args_list[0]
        self.assertEqual(feedback_args[0], self.user.user_id)
        expected_feedback_msg = "Here's the feedback on your answer:\n- Grammar/Syntax: Good grammar.\n- Legal Basis: Relevant laws cited.\n- Application: Applied well.\n- Conclusion: Clear conclusion.\nYour score: 90/100\n"
        self.assertEqual(feedback_args[1], expected_feedback_msg)


        # Verify completion message
        completion_args, completion_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(completion_args[0], self.user.user_id)
        self.assertEqual(completion_args[1], "You have completed all 8 mock exam questions! Great job!")

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
        self.assertEqual(args[1], "I'm sorry, I couldn't find any exam questions at the moment. Please try again later.")

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
    def test_admin_interruption_stops_ai_response(self, mock_get_quick_reply, mock_send_messenger_message):
        mock_get_quick_reply.return_value = "Mocked quick reply text."

        # Simulate an admin echo (user is the recipient of the admin message)
        admin_message_event = {
            'sender': {'id': self.user_id}, # Admin message is sent to the user
            'recipient': {'id': 'PAGE_ID'}, # The page is the recipient, but this is an echo
            'message': {
                'mid': 'm_test_admin',
                'text': 'Admin reply',
                'is_echo': True,
                'app_id': 123,
                'metadata': 'some metadata'
            },
            'timestamp': int(timezone.now().timestamp() * 1000) # Use timezone.now() for initial timestamp
        }

        # Define a timezone-aware datetime for comparison
        test_time_naive = datetime(2025, 1, 1, 10, 0, 0)
        test_time_aware = timezone.make_aware(test_time_naive)

        with freeze_time(test_time_naive): # freezegun works with naive datetimes
            # Process the admin echo
            process_messenger_message(admin_message_event)

            # Assert that the admin message is logged as ADMIN_MANUAL
            chat_log = ChatLog.objects.filter(user=self.user, sender_type='ADMIN_MANUAL').first()
            self.assertIsNotNone(chat_log)
            self.assertEqual(chat_log.message_content, 'Admin reply')

            # Assert user's last_admin_reply_timestamp is updated
            self.user.refresh_from_db()
            self.assertIsNotNone(self.user.last_admin_reply_timestamp)
            # Compare with timezone-aware datetime
            self.assertEqual(self.user.last_admin_reply_timestamp, test_time_aware)

            # Simulate a user message within the 10-minute window
            user_message_event = {
                'sender': {'id': self.user_id},
                'recipient': {'id': 'PAGE_ID'},
                'message': {
                    'mid': 'm_test_user',
                    'text': 'User message within 10 mins',
                    'seq': 1
                },
                'timestamp': int((test_time_aware + timedelta(minutes=5)).timestamp() * 1000) # 5 minutes after admin reply
            }

            process_messenger_message(user_message_event)

            # Assert that send_messenger_message was NOT called (AI stayed silent)
            mock_send_messenger_message.assert_not_called()

        # Advance time beyond the 10-minute window
        with freeze_time(test_time_aware + timedelta(minutes=11)): # 11 minutes after admin reply
            # Simulate another user message outside the 10-minute window
            user_message_event_after_window = {
                'sender': {'id': self.user_id},
                'recipient': {'id': 'PAGE_ID'},
                'message': {
                    'mid': 'm_test_user_after_window',
                    'text': 'User message after 10 mins',
                    'seq': 2
                },
                'timestamp': int((test_time_aware + timedelta(minutes=11)).timestamp() * 1000)
            }
            
            # Reset mock for new assertions
            mock_send_messenger_message.reset_mock()

            process_messenger_message(user_message_event_after_window)

            # Assert that send_messenger_message WAS called (AI resumed response)
            # Since the stage is GENERAL_BOT, it should send a quick reply (or echo in current task logic)
            mock_send_messenger_message.assert_called_once()
            args, kwargs = mock_send_messenger_message.call_args
            self.assertEqual(args[0], self.user_id)
            self.assertEqual("Mocked quick reply text.", args[1])


class OnboardingStageTest(TestCase):
    def setUp(self):
        # Create a new user in ONBOARDING stage with default name
        self.user_id = 'onboarding_user_psid'
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name='New User',
            current_stage='ONBOARDING'
        )

    @patch('chat.tasks.send_messenger_message')
    def test_initial_ai_introduction(self, mock_send_messenger_message):
        # Simulate an incoming message event with no message text (e.g., 'Get Started' payload)
        # Note: Messenger events can come without a 'message' field for 'get started' or postbacks.
        # Our process_messenger_message expects 'messaging_event' to contain 'message' or 'postback'.
        # For testing the 'first_name == "New User" and not message_text' path,
        # we'll simulate a message event with an empty message text first.
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_initial_no_text', 'text': ''}, # Empty text to trigger initial intro
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)
        mock_send_messenger_message.assert_called_once_with(
            self.user.user_id,
            "Hello! I'm the Law Review Center AI Chatbot, your personal study assistant. What should I call you?"
        )
        mock_send_messenger_message.reset_mock() # Reset for the next test scenario

        # Re-create user to ensure clean state for the postback test scenario
        self.user.delete()
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name='New User',
            current_stage='ONBOARDING'
        )

        # Test with postback (no message text, as postbacks are not 'messages')
        postback_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'postback': {'payload': 'GET_STARTED_PAYLOAD'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }
        process_messenger_message(postback_event)
        mock_send_messenger_message.assert_called_once_with(
            self.user.user_id,
            "Hello! I'm the Law Review Center AI Chatbot, your personal study assistant. What should I call you?"
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'ONBOARDING')
        self.assertEqual(self.user.first_name, 'New User') # Should remain 'New User' as no name was provided

    @patch('chat.tasks.send_messenger_message')
    def test_initial_onboarding_asks_for_name(self, mock_send_messenger_message):
        # Simulate an incoming message from the new user
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_initial', 'text': 'Hi'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user.user_id)
        self.assertEqual(args[1], "Nice to meet you, Hi! What is your current academic status or focus area in law (e.g., 1st year, Bar examinee, aspiring lawyer)?")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Hi') # User's name should now be 'Hi'
        self.assertEqual(self.user.current_stage, 'ONBOARDING') # Should remain in onboarding

    @patch('chat.tasks.send_messenger_message')
    def test_name_provided_asks_for_academic_status(self, mock_send_messenger_message):
        # Simulate user providing their name
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_name', 'text': 'John Doe'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user.user_id)
        self.assertEqual(args[1], "Nice to meet you, John! What is your current academic status or focus area in law (e.g., 1st year, Bar examinee, aspiring lawyer)?")
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'ONBOARDING') # Should remain in onboarding

    @patch('chat.tasks.send_messenger_message')
    def test_academic_status_provided_transitions_to_marketing(self, mock_send_messenger_message):
        # First, simulate name provided to set up the state
        self.user.first_name = 'Jane'
        self.user.save()

        # Simulate user providing academic status
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_status', 'text': '1st year law student'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user.user_id)
        self.assertEqual(args[1], "Got it! So you are focusing on 1st year law student. Let's see what I can do for you.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'MARKETING') # Should have transitioned to MARKETING


class MarketingStageTest(TestCase):
    def setUp(self):
        self.user_id = 'marketing_user_psid'
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name='MarketingUser',
            current_stage='MARKETING'
        )

    @patch('chat.tasks.send_messenger_message')
    def test_marketing_stage_initial_messages(self, mock_send_messenger_message):
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_marketing_hi', 'text': 'Hi bot'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect two messages: USP and mock exam offer
        self.assertEqual(mock_send_messenger_message.call_count, 2)
        
        # Verify the content of the first message (USP)
        call1_args, call1_kwargs = mock_send_messenger_message.call_args_list[0]
        self.assertEqual(call1_args[0], self.user_id)
        self.assertIn("personalized AI-driven feedback", call1_args[1]) # USP message

        # Verify the content of the second message (offer)
        call2_args, call2_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(call2_args[0], self.user_id)
        self.assertIn("Would you like to test your legal skills with a quick Mock Bar Exam today?", call2_args[1]) # Offer message

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'MARKETING') # Should remain in MARKETING

    @patch('chat.tasks.send_messenger_message')
    def test_marketing_stage_agrees_to_mock_exam(self, mock_send_messenger_message):
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_agree', 'text': 'Yes, start the exam'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect one message confirming exam start
        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user_id)
        self.assertIn("Great! Let's get you started with the Mock Bar Exam.", args[1])

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'MOCK_EXAM') # Should transition to MOCK_EXAM

    @patch('chat.tasks.send_messenger_message')
    def test_marketing_stage_disagrees_to_mock_exam(self, mock_send_messenger_message):
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_disagree', 'text': 'Tell me more about the center'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }
        
        process_messenger_message(user_message_event)

        # Marketing stage sends two messages: USP and mock exam offer again
        self.assertEqual(mock_send_messenger_message.call_count, 2)

        # Verify the content of the first message (USP)
        call1_args, call1_kwargs = mock_send_messenger_message.call_args_list[0]
        self.assertEqual(call1_args[0], self.user_id)
        self.assertIn("personalized AI-driven feedback", call1_args[1]) # USP message

        # Verify the content of the second message (offer)
        call2_args, call2_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(call2_args[0], self.user_id)
        self.assertIn("Would you like to test your legal skills with a quick Mock Bar Exam today?", call2_args[1]) # Offer message

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'MARKETING') # Should remain in MARKETING


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
    def test_admin_interruption_stops_ai_response(self, mock_get_quick_reply, mock_send_messenger_message):
        mock_get_quick_reply.return_value = "Mocked quick reply text."

        # Simulate an admin echo (user is the recipient of the admin message)
        admin_message_event = {
            'sender': {'id': self.user_id}, # Admin message is sent to the user
            'recipient': {'id': 'PAGE_ID'}, # The page is the recipient, but this is an echo
            'message': {
                'mid': 'm_test_admin',
                'text': 'Admin reply',
                'is_echo': True,
                'app_id': 123,
                'metadata': 'some metadata'
            },
            'timestamp': int(timezone.now().timestamp() * 1000) # Use timezone.now() for initial timestamp
        }

        # Define a timezone-aware datetime for comparison
        test_time_naive = datetime(2025, 1, 1, 10, 0, 0)
        test_time_aware = timezone.make_aware(test_time_naive)

        with freeze_time(test_time_naive): # freezegun works with naive datetimes
            # Process the admin echo
            process_messenger_message(admin_message_event)

            # Assert that the admin message is logged as ADMIN_MANUAL
            chat_log = ChatLog.objects.filter(user=self.user, sender_type='ADMIN_MANUAL').first()
            self.assertIsNotNone(chat_log)
            self.assertEqual(chat_log.message_content, 'Admin reply')

            # Assert user's last_admin_reply_timestamp is updated
            self.user.refresh_from_db()
            self.assertIsNotNone(self.user.last_admin_reply_timestamp)
            # Compare with timezone-aware datetime
            self.assertEqual(self.user.last_admin_reply_timestamp, test_time_aware)

            # Simulate a user message within the 10-minute window
            user_message_event = {
                'sender': {'id': self.user_id},
                'recipient': {'id': 'PAGE_ID'},
                'message': {
                    'mid': 'm_test_user',
                    'text': 'User message within 10 mins',
                    'seq': 1
                },
                'timestamp': int((test_time_aware + timedelta(minutes=5)).timestamp() * 1000) # 5 minutes after admin reply
            }

            process_messenger_message(user_message_event)

            # Assert that send_messenger_message was NOT called (AI stayed silent)
            mock_send_messenger_message.assert_not_called()

        # Advance time beyond the 10-minute window
        with freeze_time(test_time_aware + timedelta(minutes=11)): # 11 minutes after admin reply
            # Simulate another user message outside the 10-minute window
            user_message_event_after_window = {
                'sender': {'id': self.user_id},
                'recipient': {'id': 'PAGE_ID'},
                'message': {
                    'mid': 'm_test_user_after_window',
                    'text': 'User message after 10 mins',
                    'seq': 2
                },
                'timestamp': int((test_time_aware + timedelta(minutes=11)).timestamp() * 1000)
            }
            
            # Reset mock for new assertions
            mock_send_messenger_message.reset_mock()

            process_messenger_message(user_message_event_after_window)

            # Assert that send_messenger_message WAS called (AI resumed response)
            # Since the stage is GENERAL_BOT, it should send a quick reply (or echo in current task logic)
            mock_send_messenger_message.assert_called_once()
            args, kwargs = mock_send_messenger_message.call_args
            self.assertEqual(args[0], self.user_id)
            self.assertEqual("Mocked quick reply text.", args[1])


class GeneralBotStageTest(TestCase):
    def setUp(self):
        self.user_id = 'general_bot_user_psid'
        # User has completed mock exam and transitioned to GENERAL_BOT
        self.user = User.objects.create(
            user_id=self.user_id,
            first_name='GeneralBotUser',
            current_stage='GENERAL_BOT',
            exam_question_counter=0 # Counter is reset to 0 after exam completion
        )

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_ai_response_logged_as_system_ai(self, mock_get_quick_reply, mock_send_messenger_message):
        # Set user state to be in general bot stage after initial messages
        self.user.exam_question_counter = -1
        self.user.save()

        mock_ai_response = "This is a mocked AI quick reply."
        mock_get_quick_reply.return_value = mock_ai_response

        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_general_query', 'text': 'Tell me about contract law'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Assert that the AI response was sent
        mock_send_messenger_message.assert_called_once_with(self.user_id, mock_ai_response)

        # Assert that the AI response was logged to ChatLog
        chat_log = ChatLog.objects.filter(
            user=self.user,
            sender_type='SYSTEM_AI',
            message_content=mock_ai_response
        ).first()
        self.assertIsNotNone(chat_log, "SYSTEM_AI message was not logged.")

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.utils.ai_integration_service.get_quick_reply')
    def test_provides_registration_link_after_exam(self, mock_get_quick_reply, mock_send_messenger_message):
        # Simulate a message from the user.
        # The initial message in GENERAL_BOT stage (after exam) is triggered
        # when exam_question_counter is 0, regardless of the message content.
        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_initial_general', 'text': 'Hello'},
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        # Expect two messages: congratulatory with link, and then offer for general assistance
        self.assertEqual(mock_send_messenger_message.call_count, 2)
        
        call1_args, call1_kwargs = mock_send_messenger_message.call_args_list[0]
        self.assertEqual(call1_args[0], self.user_id)
        self.assertIn("To get full access to our comprehensive materials and more practice exams, register here:", call1_args[1])
        self.assertIn("https://www.premier.classapparelph.com/register!", call1_args[1]) # Check for the actual link

        call2_args, call2_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(call2_args[0], self.user.user_id)
        self.assertIn("I can now act as your General Legal Assistant or Mentor. How can I assist you further today?", call2_args[1])

        self.user.refresh_from_db()
        self.assertEqual(self.user.exam_question_counter, -1) # Counter should be -1 after initial message
        self.assertEqual(self.user.current_stage, 'GENERAL_BOT') # Should remain in GENERAL_BOT