from django.test import TestCase
from django.utils import timezone
from unittest import mock
from datetime import date, timedelta
import datetime as dt # Import datetime as dt to avoid conflict with datetime.datetime
from chat.models import User # Assuming User is in chat.models
from chat.utils import reset_gpt_5_2_usage_if_new_day # This will be created next

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