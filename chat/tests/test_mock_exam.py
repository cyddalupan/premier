from django.test import TestCase
from unittest.mock import patch
from chat.models import User, Question, ChatLog
from chat.tasks import process_messenger_message
from django.conf import settings
from django.utils import timezone # Import timezone utilities
import threading
import time

# Mock settings for testing
settings.MESSENGER_VERIFY_TOKEN = 'test_verify_token'
settings.OPEN_AI_TOKEN = 'test_openai_token'


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