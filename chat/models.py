from django.db import models
from legal.models import Course # Import the Course model

class User(models.Model):
    # Enum for current_stage
    STAGE_CHOICES = [
        ('ONBOARDING', 'Onboarding'),
        ('MARKETING', 'Marketing'),
        ('MOCK_EXAM', 'Mock Exam'),
        ('GENERAL_BOT', 'General Bot'),
    ]

    # Enum for onboarding_sub_stage
    ONBOARDING_SUB_STAGE_CHOICES = [
        ('ASK_NAME', 'Ask Name'),
        ('ASK_ACADEMIC_STATUS', 'Ask Academic Status'),
    ]


    user_id = models.CharField(max_length=100, primary_key=True)  # Facebook PSID
    first_name = models.CharField(max_length=255, blank=True, null=True)
    current_stage = models.CharField(
        max_length=50,
        choices=STAGE_CHOICES,
        default='ONBOARDING',
    )
    onboarding_sub_stage = models.CharField(
        max_length=50,
        choices=ONBOARDING_SUB_STAGE_CHOICES,
        null=True, # Allow null when not in ONBOARDING stage or at the very beginning
        blank=True,
    )
    exam_question_counter = models.IntegerField(default=0)  # 0-8
    last_question_id_asked = models.ForeignKey('Question', on_delete=models.SET_NULL, null=True, blank=True)
    academic_status = models.CharField(max_length=255, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)  # AI-generated summary

    last_interaction_timestamp = models.DateTimeField(blank=True, null=True)  # To trigger follow-up messages
    re_engagement_stage_index = models.IntegerField(default=0, blank=True, null=True) # Tracks the current re-engagement stage (0 for none, 1 for stage 1, etc.)
    last_re_engagement_message_sent_at = models.DateTimeField(blank=True, null=True) # Timestamp of when the last re-engagement message was sent
    is_registered_website_user = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.first_name} ({self.user_id})"

class Question(models.Model):
    CATEGORY_CHOICES = [
        ('CRIMINAL_LAW', 'Criminal Law'),
        ('CIVIL_LAW', 'Civil Law'),
        ('REMEDIAL_LAW', 'Remedial Law'),
        ('POLITICAL_LAW', 'Political Law'),
        ('LABOR_LAW', 'Labor Law'),
        ('TAX_LAW', 'Tax Law'),
        ('COMMERCIAL_LAW', 'Commercial Law'),
        ('ETHICS', 'Legal Ethics'),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, help_text="The course this question belongs to")
    question_text = models.TextField()
    expected_answer = models.TextField()


    def __str__(self):
        return f"{self.category}: {self.question_text[:50]}..."

class ChatLog(models.Model):
    SENDER_TYPE_CHOICES = [
        ('USER', 'User'),
        ('SYSTEM_AI', 'System AI'),
        ('ADMIN_MANUAL', 'Admin Manual'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE) # FK to Users
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPE_CHOICES)
    message_content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_type} - {self.user.user_id} - {self.timestamp}"


class ExamResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    score = models.IntegerField()  # Numerical score (e.g., 1-100)
    legal_writing_feedback = models.TextField(blank=True, null=True)
    legal_basis_feedback = models.TextField(blank=True, null=True)
    application_feedback = models.TextField(blank=True, null=True)
    conclusion_feedback = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Exam Result for {self.user.first_name} on Question {self.question.id} - Score: {self.score}"

class Prompt(models.Model):
    # Define choices for categories based on the identified prompt types
    CATEGORY_CHOICES = [
        ('QUICK_REPLY', 'Quick Reply'),
        ('SUMMARIZATION', 'Summarization'),
        ('EXAM_GRADING', 'Exam Grading'),
        ('RE_ENGAGEMENT', 'Re-engagement'),
        ('ASSESSMENT', 'User Strength Assessment'),
        ('NAME_EXTRACTION', 'Name Extraction'),
        # Add other categories as identified from prompts.py or FULL_PLAN.md
    ]

    name = models.CharField(max_length=255, unique=True, help_text="Unique identifier for the prompt (e.g., QUICK_REPLY_SYSTEM_PROMPT). This should match the constant name in chat/prompts.py")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, help_text="Category of the prompt (e.g., QUICK_REPLY)")
    text_content = models.TextField(help_text="The actual content of the prompt, potentially with placeholders")
    description = models.TextField(blank=True, null=True, help_text="Optional description of the prompt's purpose")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Prompt"
        verbose_name_plural = "AI Prompts"
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.category}: {self.name}"

