from django.db import models

class User(models.Model):
    # Enum for current_stage
    STAGE_CHOICES = [
        ('ONBOARDING', 'Onboarding'),
        ('MARKETING', 'Marketing'),
        ('MOCK_EXAM', 'Mock Exam'),
        ('GENERAL_BOT', 'General Bot'),
    ]

    user_id = models.CharField(max_length=100, primary_key=True)  # Facebook PSID
    first_name = models.CharField(max_length=255)
    current_stage = models.CharField(
        max_length=50,
        choices=STAGE_CHOICES,
        default='ONBOARDING',
    )
    exam_question_counter = models.IntegerField(default=0)  # 0-8
    summary = models.TextField(blank=True, null=True)  # AI-generated summary
    last_admin_reply_timestamp = models.DateTimeField(blank=True, null=True)  # For 10-minute pause logic
    last_interaction_timestamp = models.DateTimeField(blank=True, null=True)  # To trigger follow-up messages

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
    question_text = models.TextField()
    expected_answer = models.TextField()
    rubric_criteria = models.TextField()

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
