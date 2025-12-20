from django.test import TestCase
from django.db.utils import IntegrityError
from .models import Course

class CourseModelTest(TestCase):
    def setUp(self):
        # Create a course for use in multiple tests
        self.course1 = Course.objects.create(name="Criminal Law I", description="First part of criminal law")

    def test_course_creation(self):
        # Test that a course can be created
        course = Course.objects.get(name="Criminal Law I")
        self.assertEqual(course.description, "First part of criminal law")
        self.assertIsNotNone(course.created_at)
        self.assertIsNotNone(course.updated_at)

    def test_unique_course_name(self):
        # Test that course names must be unique
        with self.assertRaises(IntegrityError):
            Course.objects.create(name="Criminal Law I", description="Another criminal law course")

    def test_course_update(self):
        # Test that a course can be updated
        self.course1.name = "Criminal Law II"
        self.course1.description = "Second part of criminal law"
        self.course1.save()
        updated_course = Course.objects.get(id=self.course1.id)
        self.assertEqual(updated_course.name, "Criminal Law II")
        self.assertEqual(updated_course.description, "Second part of criminal law")
        self.assertGreater(updated_course.updated_at, updated_course.created_at) # updated_at should be newer

    def test_course_deletion(self):
        # Test that a course can be deleted
        course_id = self.course1.id
        self.course1.delete()
        with self.assertRaises(Course.DoesNotExist):
            Course.objects.get(id=course_id)

    def test_course_str_representation(self):
        # Test the __str__ method
        self.assertEqual(str(self.course1), "Criminal Law I")

    def test_course_blank_description(self):
        # Test course creation with a blank description
        course2 = Course.objects.create(name="Civil Law I")
        self.assertIsNone(course2.description)
