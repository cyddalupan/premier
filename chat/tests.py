from django.test import TestCase
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from freezegun import freeze_time
from chat.models import User, ChatLog, Question
from chat.tasks import process_messenger_message #, ai_integration_service
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
        self.assertEqual(self.user.first_name, 'John') # Should have saved first name
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
        self.user.save()

        # Mock what the AI grading service returns
        mock_grade_exam_answer.return_value = {
            'grammar_syntax_feedback': 'Good grammar.',
            'legal_basis_feedback': 'Relevant laws cited.',
            'application_feedback': 'Applied well.',
            'conclusion_feedback': 'Clear conclusion.',
            'score': 85
        }
        # Mock what get_random_exam_question returns for grading and next question
        mock_get_random_exam_question.side_effect = [self.q1, self.q2] # First for current, second for next

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
        expected_feedback_msg = "Here's the feedback on your answer:\n- Grammar Syntax Feedback: Good grammar.\n- Legal Basis Feedback: Relevant laws cited.\n- Application Feedback: Applied well.\n- Conclusion Feedback: Clear conclusion.\nYour score: 85/100"
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
        self.user.save()

        mock_grade_exam_answer.return_value = {'score': 90}
        mock_get_random_exam_question.return_value = self.q1 # For current question to grade

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
        self.assertEqual(feedback_args[0], self.user_id)
        self.assertIn("Here's the feedback on your answer:", feedback_args[1])
        self.assertIn("Your score: 90/100", feedback_args[1])

        # Verify completion message
        completion_args, completion_kwargs = mock_send_messenger_message.call_args_list[1]
        self.assertEqual(completion_args[0], self.user_id)
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
        self.assertEqual(args[0], self.user_id)
        self.assertEqual(args[1], "I'm sorry, I couldn't find any exam questions at the moment. Please try again later.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.current_stage, 'GENERAL_BOT') # Should transition out
        self.assertEqual(self.user.exam_question_counter, 0)

    @patch('chat.tasks.send_messenger_message')
    @patch('chat.stages.mock_exam.get_random_exam_question') # Patch where it's used
    def test_invalid_answer_input(self, mock_get_random_exam_question, mock_send_messenger_message):
        self.user.exam_question_counter = 1
        self.user.save()

        user_message_event = {
            'sender': {'id': self.user_id},
            'recipient': {'id': 'PAGE_ID'},
            'message': {'mid': 'm_empty_answer', 'text': ''}, # Empty answer
            'timestamp': int(timezone.now().timestamp() * 1000)
        }

        process_messenger_message(user_message_event)

        mock_send_messenger_message.assert_called_once()
        args, kwargs = mock_send_messenger_message.call_args
        self.assertEqual(args[0], self.user_id)
        self.assertEqual(args[1], "Please provide your answer to the last question.")

        self.user.refresh_from_db()
        self.assertEqual(self.user.exam_question_counter, 1) # Should remain in current question
        self.assertEqual(self.user.current_stage, 'MOCK_EXAM')
