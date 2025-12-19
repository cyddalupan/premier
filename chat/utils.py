from .ai_integration import AIIntegration
from .models import Question
import random
import logging

logger = logging.getLogger(__name__)

# Initialize AIIntegration outside tasks to reuse the instance
ai_integration_service = AIIntegration()

def get_random_exam_question():
    """
    Retrieves a random question from the Question bank, ensuring it has all necessary fields.
    """
    questions = Question.objects.filter(
        expected_answer__isnull=False
    ).exclude(
        expected_answer__exact=''
    )

    if questions.exists():
        return random.choice(questions)

    logger.warning("No valid exam questions found with complete data (expected_answer).")
    return None

def generate_persuasion_messages(user, context):
    """
    Generates persuasion messages based on user registration status and context.
    """
    messages = []
    website_link = "https://www.premierreviewcenter.com" # Placeholder, should be from settings

    if user.is_registered_website_user:
        # User is already registered, offer encouragement or next steps on the website
        if context == 'exam_finished':
            messages.append(f"Excellent work, {user.first_name}! Since you're already a registered user, you can find more advanced practice exams and personalized analytics on our website: {website_link}")
        elif context == 'exam_opt_out':
            messages.append(f"I understand, {user.first_name}. Remember, as a registered user, you have access to a wealth of resources at {website_link} to help you at your own pace.")
        elif context == 'general_chat':
            messages.append(f"Just a friendly reminder, {user.first_name}, you can always access exclusive content and support on our website: {website_link}")
    else:
        # User is not registered, actively persuade them to register
        if context == 'exam_finished':
            messages.append(f"Congratulations on completing the mock exam, {user.first_name}! To unlock comprehensive study materials, detailed performance analytics, and even more practice questions, register for free at our Review Center website: {website_link}")
            messages.append("It's the best way to prepare for the bar exam!")
        elif context == 'exam_opt_out':
            messages.append(f"I understand, {user.first_name}. Taking a break is perfectly fine! However, don't miss out on hundreds of practice questions, in-depth legal discussions, and personalized study plans. Visit our Review Center website and register for free to boost your preparation: {website_link}")
            messages.append("You can continue your review anytime, at your own pace.")
        elif context == 'general_chat':
            messages.append(f"Are you looking for more resources or detailed explanations, {user.first_name}? Our Review Center website offers an extensive library of legal materials and practice tools. Register for free today: {website_link}")
            messages.append("It's a powerful tool to enhance your bar exam preparation!")
    
    return messages

