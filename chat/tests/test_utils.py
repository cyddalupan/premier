from django.test import TestCase
from django.utils import timezone
from unittest import mock
from datetime import date, timedelta
import datetime as dt # Import datetime as dt to avoid conflict with datetime.datetime
from chat.models import User # Assuming User is in chat.models
from chat.utils import reset_gpt_5_2_usage_if_new_day, generate_persuasion_messages # Import generate_persuasion_messages
from django.conf import settings # Import settings to access REVIEW_CENTER_WEBSITE_URL

class GeneratePersuasionMessagesTest(TestCase):
    def setUp(self):
        self.website_url = settings.REVIEW_CENTER_WEBSITE_URL

        self.unregistered_user = User.objects.create(
            user_id='unregistered_user',
            first_name='Unreg',
            is_registered_website_user=False,
        )
        self.registered_user = User.objects.create(
            user_id='registered_user',
            first_name='Reg',
            is_registered_website_user=True,
        )

    def test_unregistered_user_exam_finished_persuasion(self):
        messages = generate_persuasion_messages(self.unregistered_user, 'exam_finished')
        self.assertTrue(len(messages) >= 2) # Expect at least two messages

        # First message for unregistered exam_finished
        self.assertIn(self.website_url, messages[0])
        self.assertIn("register for free", messages[0].lower()) # Still expect this in the main persuasion message

        # Second message for unregistered exam_finished - only check URL
        self.assertIn(self.website_url, messages[1])

    def test_registered_user_exam_finished_persuasion(self):
        messages = generate_persuasion_messages(self.registered_user, 'exam_finished')
        self.assertTrue(len(messages) > 0)
        for message in messages:
            self.assertIn(self.website_url, message)
            self.assertIn("find more advanced practice exams and personalized analytics", message.lower())

    def test_unregistered_user_exam_opt_out_persuasion(self):
        messages = generate_persuasion_messages(self.unregistered_user, 'exam_opt_out')
        self.assertTrue(len(messages) >= 2) # Expect at least two messages

        # First message for unregistered exam_opt_out
        self.assertIn(self.website_url, messages[0])
        self.assertIn("don't miss out on hundreds of practice questions", messages[0].lower())

        # Second message for unregistered exam_opt_out - only check URL
        self.assertIn(self.website_url, messages[1])

    def test_registered_user_exam_opt_out_persuasion(self):
        messages = generate_persuasion_messages(self.registered_user, 'exam_opt_out')
        self.assertTrue(len(messages) > 0)
        for message in messages:
            self.assertIn(self.website_url, message)
            self.assertIn("access to a wealth of resources", message.lower())

    def test_unregistered_user_general_chat_persuasion(self):
        messages = generate_persuasion_messages(self.unregistered_user, 'general_chat')
        self.assertTrue(len(messages) >= 2) # Expect at least two messages

        # First message for unregistered general_chat
        self.assertIn(self.website_url, messages[0])
        self.assertIn("extensive library of legal materials and practice tools", messages[0].lower())

        # Second message for unregistered general_chat - only check URL
        self.assertIn(self.website_url, messages[1])

    def test_registered_user_general_chat_persuasion(self):
        messages = generate_persuasion_messages(self.registered_user, 'general_chat')
        self.assertTrue(len(messages) > 0)
        for message in messages:
            self.assertIn(self.website_url, message)
            self.assertIn("access exclusive content and support", message.lower())

class ResetGPT52UsageTest(TestCase):
    def setUp(self):
        # Create a user with initial values for testing resets
        self.user = User.objects.create(
            user_id='test_user_reset',
            gpt_5_2_daily_count=5,
            gpt_5_2_last_reset_date=date.today() - timedelta(days=1) # Set to yesterday initially
        )

    @mock.patch('django.utils.timezone.now')
    def test_reset_on_new_day(self, mock_now):
        # Simulate today being a new day (e.g., current date is different from last_reset_date)
        mock_now.return_value = dt.datetime(2025, 1, 1, 10, 0, 0, tzinfo=dt.timezone.utc)
        
        # Manually set user's last reset date to a past date (e.g., Dec 31, 2024)
        self.user.gpt_5_2_last_reset_date = date(2024, 12, 31)
        self.user.gpt_5_2_daily_count = 10 # Set some count
        self.user.save()

        reset_gpt_5_2_usage_if_new_day(self.user)
        self.user.refresh_from_db()

        self.assertEqual(self.user.gpt_5_2_daily_count, 0)
        self.assertEqual(self.user.gpt_5_2_last_reset_date, date(2025, 1, 1))

    @mock.patch('django.utils.timezone.now')
    def test_no_reset_on_same_day(self, mock_now):
        # Simulate today being the same day as last_reset_date
        mock_now.return_value = dt.datetime(2025, 1, 1, 10, 0, 0, tzinfo=dt.timezone.utc)
        
        # Manually set user's last reset date to today (Jan 1, 2025)
        self.user.gpt_5_2_last_reset_date = date(2025, 1, 1)
        self.user.gpt_5_2_daily_count = 7 # Set some count
        self.user.save()

        reset_gpt_5_2_usage_if_new_day(self.user)
        self.user.refresh_from_db()

        self.assertEqual(self.user.gpt_5_2_daily_count, 7) # Should remain 7
        self.assertEqual(self.user.gpt_5_2_last_reset_date, date(2025, 1, 1))