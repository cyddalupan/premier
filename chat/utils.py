import random
import logging
from .models import Question, User # Added import for Question model, User model for GPT-5.2 usage tracking
from django.utils import timezone # Added import for timezone
import chat.prompts # Import for LOADING_MESSAGES

logger = logging.getLogger(__name__)

# ai_integration_service will now be imported and instantiated directly where needed
# e.g., in tasks.py or tests.py to avoid circular dependencies.

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

def get_random_loading_message() -> str:
    """
    Returns a random loading message from the predefined list.
    """
    return random.choice(chat.prompts.LOADING_MESSAGES)

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

from django.core.cache import cache
from .models import Prompt
import chat.prompts # Import the module containing fallback prompts

def get_prompt(name: str, category: str, use_fallback: bool = True) -> str:
    """
    Retrieves a prompt, prioritizing the database, then cache, then falling back to code.
    Args:
        name (str): The unique name of the prompt (e.g., 'QUICK_REPLY_SYSTEM_PROMPT').
        category (str): The category of the prompt (e.g., 'QUICK_REPLY').
        use_fallback (bool): Whether to use the hardcoded prompts as a fallback if not found in DB/cache.

    Returns:
        str: The content of the prompt.

    Raises:
        ValueError: If the prompt is not found in the database, cache, or code fallback.
    """
    cache_key = f"prompt:{category}:{name}"
    prompt_content = cache.get(cache_key)

    if prompt_content is not None:
        return prompt_content

    try:
        db_prompt = Prompt.objects.get(name=name, category=category)
        prompt_content = db_prompt.text_content
        cache.set(cache_key, prompt_content, timeout=3600)  # Cache for 1 hour
        return prompt_content
    except Prompt.DoesNotExist:
        logger.warning(f"Prompt '{name}' (Category: {category}) not found in database. Attempting code fallback.")
        if use_fallback:
            try:
                # Attempt to get from chat.prompts module
                prompt_content = getattr(chat.prompts, name)
                cache.set(cache_key, prompt_content, timeout=3600)  # Cache for 1 hour
                return prompt_content
            except AttributeError:
                pass # Fall through to ValueError
        raise ValueError(f"Prompt '{name}' (Category: {category}) not found in database or code fallback.")

def reset_gpt_5_2_usage_if_new_day(user: User):
    """
    Resets the user's gpt_5_2_daily_count if a new UTC day has started.
    """
    today_utc = timezone.now().date()
    if user.gpt_5_2_last_reset_date != today_utc:
        user.gpt_5_2_daily_count = 0
        user.gpt_5_2_last_reset_date = today_utc
        user.save()
        logger.info(f"User {user.user_id}: GPT-5.2 daily count reset for a new day.")



