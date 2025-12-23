from django.test import TestCase
from unittest.mock import patch, MagicMock
from chat.models import Question, Prompt, User
from legal.models import Course # Import Course model for testing
from django.core.cache import cache
from django.db.utils import IntegrityError
from django.db import transaction # Import transaction
from chat.utils import get_prompt
import chat.prompts # Global import for chat.prompts


class QuestionModelCourseIntegrationTest(TestCase):
    def setUp(self):
        from legal.models import Course # Import Course model for testing
        self.course1 = Course.objects.create(name="Criminal Law", description="Course on Criminal Law")
        self.course2 = Course.objects.create(name="Civil Law", description="Course on Civil Law")

        self.question_no_course = Question.objects.create(
            category='ETHICS',
            question_text='A question without a specific course?',
            expected_answer='Answer for no course'
        )
        self.question_crim_1 = Question.objects.create(
            category='CRIMINAL_LAW',
            question_text='Criminal Law Question 1?',
            expected_answer='Answer for Crim 1',
            course=self.course1
        )
        self.question_crim_2 = Question.objects.create(
            category='CRIMINAL_LAW',
            question_text='Criminal Law Question 2?',
            expected_answer='Answer for Crim 2',
            course=self.course1
        )
        self.question_civil_1 = Question.objects.create(
            category='CIVIL_LAW',
            question_text='Civil Law Question 1?',
            expected_answer='Answer for Civil 1',
            course=self.course2
        )

    def test_question_can_be_assigned_to_course(self):
        self.assertEqual(self.question_crim_1.course, self.course1)
        self.assertEqual(self.question_civil_1.course, self.course2)

    def test_question_without_course_is_null(self):
        self.assertIsNone(self.question_no_course.course)

    def test_filter_questions_by_course(self):
        criminal_questions = Question.objects.filter(course=self.course1)
        self.assertEqual(criminal_questions.count(), 2)
        self.assertIn(self.question_crim_1, criminal_questions)
        self.assertIn(self.question_crim_2, criminal_questions)
        self.assertNotIn(self.question_civil_1, criminal_questions)

        civil_questions = Question.objects.filter(course=self.course2)
        self.assertEqual(civil_questions.count(), 1)
        self.assertIn(self.question_civil_1, civil_questions)
        self.assertNotIn(self.question_crim_1, civil_questions)

        no_course_questions = Question.objects.filter(course__isnull=True)
        self.assertEqual(no_course_questions.count(), 1)
        self.assertIn(self.question_no_course, no_course_questions)

    def test_on_delete_set_null_behavior(self):
        # Create a new course and question for this specific test
        course_to_delete = Course.objects.create(name="Course to Delete")
        question_to_check = Question.objects.create(
            category='ETHICS',
            question_text='Question for deleted course?',
            expected_answer='Answer',
            course=course_to_delete
        )

        self.assertEqual(question_to_check.course, course_to_delete)

        # Delete the course
        course_to_delete.delete()

        # Refresh the question from the database
        question_to_check.refresh_from_db()

        # Assert that the course field is now None
        self.assertIsNone(question_to_check.course)
        # Assert that the question itself was not deleted
        self.assertIsNotNone(question_to_check.id)

class PromptRetrievalTest(TestCase):
    def setUp(self):
        # Clear cache before each test
        cache.clear()
        # Ensure no prompts exist in DB initially
        Prompt.objects.all().delete()

        self.test_prompt_name = "TEST_SYSTEM_PROMPT"
        self.test_prompt_category = "TEST_CATEGORY"
        self.test_prompt_content_db = "This is a test prompt from the database."
        self.test_prompt_content_code = "This is a test prompt from code."

        # Dynamically add a temporary constant to chat.prompts for fallback test
        setattr(chat.prompts, self.test_prompt_name, self.test_prompt_content_code)

    def tearDown(self):
        # Clean up dynamically added constant
        if hasattr(chat.prompts, self.test_prompt_name):
            delattr(chat.prompts, self.test_prompt_name)
        cache.clear()
        Prompt.objects.all().delete()


    def test_get_prompt_from_database(self):
        # Create a prompt in the database
        Prompt.objects.create(
            name=self.test_prompt_name,
            category=self.test_prompt_category,
            text_content=self.test_prompt_content_db
        )

        # Retrieve the prompt
        retrieved_content = get_prompt(name=self.test_prompt_name, category=self.test_prompt_category)
        self.assertEqual(retrieved_content, self.test_prompt_content_db)

        # Ensure it's now in cache
        self.assertEqual(cache.get(f"prompt:{self.test_prompt_category}:{self.test_prompt_name}"), self.test_prompt_content_db)

    def test_get_prompt_from_cache(self):
        # Put prompt directly into cache
        cache.set(f"prompt:{self.test_prompt_category}:{self.test_prompt_name}", self.test_prompt_content_db)

        # Ensure DB is empty (should not be hit)
        Prompt.objects.all().delete()

        # Retrieve the prompt
        retrieved_content = get_prompt(name=self.test_prompt_name, category=self.test_prompt_category)
        self.assertEqual(retrieved_content, self.test_prompt_content_db)

    def test_get_prompt_from_code_fallback(self):
        # Ensure prompt is not in DB or cache
        Prompt.objects.all().delete()
        cache.clear()

        # Retrieve the prompt (should fall back to code)
        retrieved_content = get_prompt(name=self.test_prompt_name, category=self.test_prompt_category)
        self.assertEqual(retrieved_content, self.test_prompt_content_code)

        # Ensure it's now in cache after fallback
        self.assertEqual(cache.get(f"prompt:{self.test_prompt_category}:{self.test_prompt_name}"), self.test_prompt_content_code)

    def test_get_prompt_not_found(self):
        # Ensure prompt is not in DB, cache, or code fallback
        Prompt.objects.all().delete()
        cache.clear()
        if hasattr(chat.prompts, self.test_prompt_name):
            delattr(chat.prompts, self.test_prompt_name) # Ensure no code fallback

        with self.assertRaises(ValueError):
            get_prompt(name=self.test_prompt_name, category=self.test_prompt_category)

    def test_get_prompt_not_found_no_fallback(self):
        # Create a prompt in the database
        Prompt.objects.create(
            name=self.test_prompt_name,
            category=self.test_prompt_category,
            text_content=self.test_prompt_content_db
        )
        # Attempt to retrieve with use_fallback=False when not in cache (should hit DB, but for this test we want to avoid fallback)
        cache.clear()

        # Try to retrieve a prompt that exists in DB but not in code and explicitly disable fallback
        # This test ensures that if use_fallback is False, it won't even look for it in chat.prompts.
        # But if it is in DB, it should still return. Let's create a scenario where it's NOT in DB.
        non_existent_name = "NON_EXISTENT_PROMPT"
        with self.assertRaises(ValueError):
            get_prompt(name=non_existent_name, category=self.test_prompt_category, use_fallback=False)

        # Test case where it's in DB, but we explicitly disabled fallback (should still return from DB)
        retrieved_content = get_prompt(name=self.test_prompt_name, category=self.test_prompt_category, use_fallback=False)
        self.assertEqual(retrieved_content, self.test_prompt_content_db)


    def test_prompt_model_creation(self):
        prompt = Prompt.objects.create(
            name="MODEL_TEST_PROMPT",
            category="MODEL_TEST",
            text_content="Content for model test."
        )
        self.assertIsNotNone(prompt.pk)
        self.assertEqual(prompt.name, "MODEL_TEST_PROMPT")
        self.assertEqual(prompt.category, "MODEL_TEST")
        self.assertEqual(prompt.text_content, "Content for model test.")
        self.assertIsNotNone(prompt.created_at)
        self.assertIsNotNone(prompt.updated_at)
        self.assertEqual(str(prompt), "MODEL_TEST: MODEL_TEST_PROMPT")

    def test_prompt_model_unique_name(self):
        Prompt.objects.create(
            name=self.test_prompt_name,
            category=self.test_prompt_category,
            text_content=self.test_prompt_content_db
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic(): # Use atomic block to isolate the transaction
                Prompt.objects.create(
                    name=self.test_prompt_name,
                    category="OTHER_CATEGORY",
                    text_content="Duplicate name content"
                )

    def test_prompt_model_update_timestamp(self):
        prompt = Prompt.objects.create(
            name="UPDATE_TEST_PROMPT",
            category="UPDATE_TEST",
            text_content="Initial content."
        )
        old_updated_at = prompt.updated_at
        prompt.text_content = "Updated content."
        prompt.save()
        self.assertGreater(prompt.updated_at, old_updated_at)


import datetime
from django.utils import timezone

class UserGPT52UsageTest(TestCase):
    def test_user_has_gpt_5_2_usage_fields(self):
        user = User.objects.create(user_id='test_user_gpt_fields')
        self.assertTrue(hasattr(user, 'gpt_5_2_daily_count'))
        self.assertTrue(hasattr(user, 'gpt_5_2_last_reset_date'))

    def test_gpt_5_2_daily_count_default_value(self):
        user = User.objects.create(user_id='test_user_gpt_count_default')
        self.assertEqual(user.gpt_5_2_daily_count, 0)

    def test_gpt_5_2_last_reset_date_default_value(self):
        user = User.objects.create(user_id='test_user_gpt_date_default')
        user.refresh_from_db() # Ensure we are getting the value as stored in DB
        self.assertEqual(user.gpt_5_2_last_reset_date, timezone.now().date())

    def test_set_and_get_gpt_5_2_usage_fields(self):
        user = User.objects.create(user_id='test_user_gpt_set_get')
        user.gpt_5_2_daily_count = 5
        user.gpt_5_2_last_reset_date = datetime.date(2024, 1, 1)
        user.save()

        retrieved_user = User.objects.get(user_id='test_user_gpt_set_get')
        self.assertEqual(retrieved_user.gpt_5_2_daily_count, 5)
        self.assertEqual(retrieved_user.gpt_5_2_last_reset_date, datetime.date(2024, 1, 1))

    def test_gpt_5_2_daily_count_can_exceed_limit_temporarily(self):
        # This test ensures the field itself can store values beyond 10,
        # the limit enforcement will be in business logic.
        user = User.objects.create(user_id='test_user_gpt_exceed_limit')
        user.gpt_5_2_daily_count = 15
        user.save()
        retrieved_user = User.objects.get(user_id='test_user_gpt_exceed_limit')
        self.assertEqual(retrieved_user.gpt_5_2_daily_count, 15)