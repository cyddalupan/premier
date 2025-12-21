from django.test import TestCase
from unittest.mock import patch, MagicMock
import unittest.mock as mock
from datetime import datetime, timedelta
from freezegun import freeze_time
from chat.models import User, ChatLog # Import ChatLog as well
from chat.tasks import check_inactive_users, process_messenger_message
from django.conf import settings
from django.utils import timezone # Import timezone utilities

# Mock settings for testing
settings.MESSENGER_VERIFY_TOKEN = 'test_verify_token'
settings.OPEN_AI_TOKEN = 'test_openai_token'


class TestReEngagementCron(TestCase):
    def setUp(self):
        self.fixed_now = timezone.make_aware(datetime(2025, 1, 1, 12, 0, 0)) # Fixed time for setUp
        self.now = self.fixed_now # Align self.now with the fixed time
        
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
    @patch('chat.tasks.ai_integration_service.generate_re_engagement_message', return_value='AI-composed re-engagement message!')
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
            first_name=self.inactive_user_general.first_name,
            current_stage=self.inactive_user_general.current_stage,
            user_summary=self.inactive_user_general.summary,
            conversation_history=mock.ANY
        )
        mock_generate_message.assert_any_call(
            user_id=self.inactive_user_marketing.user_id,
            first_name=self.inactive_user_marketing.first_name,
            current_stage=self.inactive_user_marketing.current_stage,
            user_summary=self.inactive_user_marketing.summary,
            conversation_history=mock.ANY
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
    @patch('chat.tasks.ChatLog.objects.create')
    @patch('chat.tasks.send_messenger_message')
    @patch('chat.tasks.ai_integration_service.generate_re_engagement_message')
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
    @patch('chat.tasks.ai_integration_service.generate_re_engagement_message')
    @patch('chat.models.User.objects.filter') # Patch User.objects.filter
    def test_multi_stage_re_engagement_flow(self, mock_user_filter, mock_generate_message, mock_chat_log_create, mock_send_message):
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
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()
            
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
        new_last_interaction_time = user.last_interaction_timestamp

        # --- Test 2: Still within Stage 1's *interval*, but message already sent and last_interaction_timestamp updated ---
        # The user's last_interaction_timestamp is now `new_last_interaction_time` (which is 1h30m after initial)
        # We need to check a point within (new_last_interaction_time + 1min) for example, where overall inactivity is still within (1,2]
        # But `re_engagement_stage_index` is already 1, so no new message should be sent.
        with freeze_time(new_last_interaction_time + timedelta(minutes=10)):
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()

            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_generate_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 1) # Should remain 1
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time) # Should not be updated


        # --- Test 3: Passed Stage 1, but still before Stage 2 ---
        with freeze_time(initial_interaction_time + timedelta(hours=3)):
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()

            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 1) # Should remain 1
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time) # Should not be updated


        # --- Test 4: Passed Stage 1, but still before Stage 2 ---
        with freeze_time(initial_interaction_time + timedelta(hours=3)):
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()

            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 1) # Should remain 1
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time) # Should not be updated


        # --- Test 5: Stage 2: 5 hours 30 minutes (within 5-6 hour window) ---
        with freeze_time(initial_interaction_time + timedelta(hours=5, minutes=30)):
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()

            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 1)
            mock_send_message.assert_called_once_with(user.user_id, 'Re-engagement message AI content')
            self.assertEqual(mock_generate_message.call_count, 1)
            self.assertEqual(mock_chat_log_create.call_count, 1)
            self.assertEqual(user.re_engagement_stage_index, 2)
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time)
        new_last_interaction_time = user.last_interaction_timestamp


        # --- Test 6: Stage 3: 11 hours 45 minutes (within 11-12 hour window) ---
        with freeze_time(initial_interaction_time + timedelta(hours=11, minutes=45)):
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()

            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 1)
            mock_send_message.assert_called_once_with(user.user_id, 'Re-engagement message AI content')
            self.assertEqual(mock_generate_message.call_count, 1)
            self.assertEqual(mock_chat_log_create.call_count, 1)
            self.assertEqual(user.re_engagement_stage_index, 3)
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time)
        new_last_interaction_time = user.last_interaction_timestamp


        # --- Test 7: Stage 4: 21 hours 15 minutes (within 21-22 hour window) ---
        with freeze_time(initial_interaction_time + timedelta(hours=21, minutes=15)):
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()

            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 1)
            mock_send_message.assert_called_once_with(user.user_id, 'Re-engagement message AI content')
            self.assertEqual(mock_generate_message.call_count, 1)
            self.assertEqual(mock_chat_log_create.call_count, 1)
            self.assertEqual(user.re_engagement_stage_index, 4)
            self.assertEqual(user.last_interaction_timestamp, new_last_interaction_time)
        last_re_engagement_time = user.last_interaction_timestamp


        # --- Test 8: After all stages: 25 hours (no more re-engagement from this flow) ---
        with freeze_time(initial_interaction_time + timedelta(hours=25)):
            # Reset mocks for this stage to ensure assertions are clean
            mock_send_message.reset_mock()
            mock_generate_message.reset_mock()
            mock_chat_log_create.reset_mock()

            check_inactive_users()
            user.refresh_from_db()
            self.assertEqual(mock_send_message.call_count, 0)
            self.assertEqual(mock_generate_message.call_count, 0)
            self.assertEqual(mock_chat_log_create.call_count, 0)
            self.assertEqual(user.re_engagement_stage_index, 4) # Should remain 4
            self.assertEqual(user.last_interaction_timestamp, last_re_engagement_time) # Should not be updated


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
